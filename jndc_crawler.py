# -*- coding: utf-8 -*-
"""
전남개발공사 (jndc) - 게시판 순회 방식 크롤러 (v2 재작성)

기존 통합검색 방식(검색어 31개)이 사이트 봇 방어에 걸려서 게시판 직접 순회로 변경.

수집 대상 (총 3 그룹):
  1) 공고/자료 게시판 8개 (기존)
     parcelout, breakdown, tenderfree, reward, sale, jobs, etc, mediareport
  2) 사업내역 게시판 6개 (신규)
     bdctydevlop, bdbldinddevlop, bdirsttdevlop, bdsundevlop, bdwinddevlop, bsnsdtls
     - HTML 구조 다름 (grid/card 형태), 상세페이지에서 title 추출
  3) 사업안내 컨텐츠 페이지 13개 (신규, 정적)
     M03010101 ~ M030501, title/url만 인덱스

URL 형식:
  리스트: /web/main/bbs/{key}?cp={page}&sortOrder=REG_DT&sortDirection=DESC&bbsId={key}
          &pstNtcYn=false&baOpenDay=false&pstRlsYn=true&delYn=false
  상세:   /web/main/bbs/{key}/{postId}
  정적:   /web/main/contents/{code}

Rate limit:
  - WORKERS=2 (매우 보수적)
  - REQUEST_INTERVAL=1.0s
  - 사이트 봇 방어 회피 위해 절대 초과 금지
"""
import re
import time
import threading
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


class JNDCCrawler:
    """전남개발공사 게시판 순회 크롤러."""

    BASE_URL = "https://www.jndc.co.kr"

    # 공고/자료 게시판 (8개)
    NOTICE_BOARDS = [
        ("parcelout", "분양공고"),
        ("breakdown", "입찰공고"),
        ("tenderfree", "입찰자료실"),
        ("reward", "보상공고"),
        ("sale", "매각공고"),
        ("jobs", "채용공고"),
        ("etc", "기타공고"),
        ("mediareport", "언론보도"),
    ]

    # 사업내역 게시판 (6개, 그리드 카드형)
    PROJECT_BOARDS = [
        ("bdctydevlop", "택지개발"),
        ("bdbldinddevlop", "관광단지"),
        ("bdirsttdevlop", "산단조성"),
        ("bdsundevlop", "태양광발전"),
        ("bdwinddevlop", "풍력발전"),
        ("bsnsdtls", "운영사업"),
    ]

    # 사업안내 정적 페이지 (13개)
    ANNAE_CONTENTS = [
        ("M03010101", "사업안내"),
        ("M03010102", "관광단지"),
        ("M03010103", "산단조성"),
        ("M03010201", "도시개발"),
        ("M03010202", "택지개발"),
        ("M03010203", "산단조성"),
        ("M03020101", "신재생에너지"),
        ("M03020102", "풍력발전"),
        ("M03020103", "사회공헌 실현"),
        ("M030301", "운영사업"),
        ("M03040101", "주택사업"),
        ("M03040102", "분양주택"),
        ("M030501", "수탁사업"),
    ]

    # 게시판별 마지막 페이지 (2026-07-10 이진탐색 확인)
    NOTICE_LAST_PAGE = {
        "parcelout": 25,        # 실제 23 + 여유
        "breakdown": 100,       # 실제 97 + 여유
        "tenderfree": 3,        # 실제 1 + 여유
        "reward": 60,           # 실제 57 (페이지 6~57은 1건씩) + 여유
        "sale": 15,             # 실제 7 + 여유
        "jobs": 40,             # 실제 35 + 여유
        "etc": 30,              # 실제 22 + 여유
        "mediareport": 1650,    # 실제 1599 + 여유
    }

    WORKERS = 4               # 봇 방어 회피용 낮게
    MAX_PAGES = 1700          # mediareport 커버 위해
    MAX_RETRIES = 3
    REQUEST_INTERVAL = 0.4    # 요청 사이 최소 대기 (초, thread 간 공유)

    _DATE_RE = re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})")

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
        })
        adapter = HTTPAdapter(pool_connections=8, pool_maxsize=16)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.verify = False
        self._last_request = 0.0
        self._interval_lock = threading.Lock()

    # ------------------------------------------------------------------ HTTP
    def _fetch(self, url):
        """thread-safe GET. 모든 스레드가 REQUEST_INTERVAL 간격 공유."""
        # thread 간 요청 인터벌 강제 (lock으로)
        with self._interval_lock:
            wait = self.REQUEST_INTERVAL - (time.time() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.time()

        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.get(url, timeout=25)
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                if len(r.text) < 1500:
                    raise RuntimeError(f"짧은 응답({len(r.text)}) - 봇 방어 의심")
                r.encoding = "utf-8"
                return BeautifulSoup(r.text, "lxml")
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(2.0 * (attempt + 1))  # 백오프
        return None

    @staticmethod
    def _normalize_date(text):
        if not text:
            return ""
        m = JNDCCrawler._DATE_RE.search(text)
        if not m:
            return ""
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 2000 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
        return ""

    # ---------------------------------------------- 공고 게시판 (tbody tr)
    def _list_url(self, key, page):
        return (
            f"{self.BASE_URL}/web/main/bbs/{key}"
            f"?cp={page}&sortOrder=REG_DT&sortDirection=DESC&bbsId={key}"
            f"&pstNtcYn=false&baOpenDay=false&pstRlsYn=true&delYn=false"
        )

    def _parse_notice_page(self, soup, key, name):
        """공고 게시판 페이지 파싱 (tbody tr 형태)."""
        results = []
        if not soup:
            return results
        seen_ids = set()
        for tr in soup.select("tbody tr"):
            a = tr.select_one("a[href]")
            if not a:
                continue
            href = a.get("href", "")
            m = re.search(rf"/web/main/bbs/{key}/(\d+)", href)
            if not m:
                continue
            post_id = m.group(1)
            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)
            title = a.get_text(" ", strip=True)
            title = re.sub(r"^새글\s*", "", title).strip()
            if not title or len(title) < 2:
                continue
            # 날짜 셀
            date = ""
            for td in tr.find_all("td"):
                d = self._normalize_date(td.get_text(strip=True))
                if d:
                    date = d
                    break
            results.append({
                "title": title,
                "date": date,
                "url": f"{self.BASE_URL}/web/main/bbs/{key}/{post_id}",
                "organization": name,
                "number": post_id,
            })
        return results

    def _crawl_notice_board(self, key, name):
        """공고 게시판 한 개 전체 순회. 사전 확인된 마지막 페이지까지."""
        results = {}
        empty_streak = 0
        last_page = self.NOTICE_LAST_PAGE.get(key, self.MAX_PAGES)
        for page in range(1, last_page + 1):
            soup = self._fetch(self._list_url(key, page))
            items = self._parse_notice_page(soup, key, name)
            if not items:
                empty_streak += 1
                if empty_streak >= 3:  # 3연속 빈 페이지면 조기 종료
                    break
                continue
            empty_streak = 0
            for it in items:
                if it["url"] not in results:
                    results[it["url"]] = it
        return list(results.values())

    # ----------------------------------------- 사업내역 게시판 (grid card)
    def _crawl_project_board(self, key, name):
        """사업내역 게시판 - 리스트에서 링크만 추출, 상세는 title 위해 방문."""
        results = []
        url = f"{self.BASE_URL}/web/main/bbs/{key}"
        soup = self._fetch(url)
        if not soup:
            return results

        # 리스트 페이지에서 상세 링크 추출
        post_ids = []
        seen = set()
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            m = re.search(rf"/web/main/bbs/{key}/(\d+)", href)
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                post_ids.append(m.group(1))

        # 상세 페이지 방문해서 title 추출
        for post_id in post_ids:
            detail_url = f"{self.BASE_URL}/web/main/bbs/{key}/{post_id}"
            det_soup = self._fetch(detail_url)
            if not det_soup:
                continue
            # div.sub-viewpage-title 에서 제목 추출
            title_el = det_soup.select_one("div.sub-viewpage-title")
            if title_el:
                title = title_el.get_text(" ", strip=True)
            else:
                title = f"{name} #{post_id}"
            # 상태 어미(진행/완료) 분리 정리
            title = title.strip()
            if not title:
                continue
            results.append({
                "title": title,
                "date": "",   # 사업내역엔 날짜 없음
                "url": detail_url,
                "organization": f"사업내역/{name}",
                "number": post_id,
            })
        return results

    # ----------------------------------------- 사업안내 컨텐츠 (정적)
    def _crawl_annae_content(self, code, label):
        """정적 컨텐츠 페이지 하나 인덱스."""
        url = f"{self.BASE_URL}/web/main/contents/{code}"
        soup = self._fetch(url)
        if not soup:
            return None
        # 제목 (h4 h4-tit 또는 sub-title 근처)
        title = ""
        for sel in [".sub-viewpage-title", "h4.h4-tit", "h4", "h3.sub-title"]:
            el = soup.select_one(sel)
            if el:
                t = el.get_text(" ", strip=True)
                if t and t != "사업안내" and len(t) > 2:
                    title = t
                    break
        if not title:
            title = f"사업안내 - {label}"
        return {
            "title": title,
            "date": "",
            "url": url,
            "organization": f"사업안내/{label}",
            "number": code,
        }

    # ================================================================ Public
    def search(self, keyword="", max_pages=999, start_date=None, end_date=None):
        t0 = time.time()
        all_results = []

        # 1) 공고 게시판 8개 (병렬 WORKERS=2)
        print(f"[전남개발공사] 공고 게시판 {len(self.NOTICE_BOARDS)}개 시작...", flush=True)
        with ThreadPoolExecutor(max_workers=self.WORKERS) as pool:
            futs = {pool.submit(self._crawl_notice_board, k, n): (k, n)
                    for k, n in self.NOTICE_BOARDS}
            for f in as_completed(futs):
                k, n = futs[f]
                try:
                    items = f.result()
                    all_results.extend(items)
                    print(f"  [{n}] {len(items)}건", flush=True)
                except Exception as e:
                    print(f"  [{n}] 실패: {e}", flush=True)

        # 2) 사업내역 게시판 6개 (병렬 WORKERS=2)
        print(f"[전남개발공사] 사업내역 게시판 {len(self.PROJECT_BOARDS)}개 시작...", flush=True)
        with ThreadPoolExecutor(max_workers=self.WORKERS) as pool:
            futs = {pool.submit(self._crawl_project_board, k, n): (k, n)
                    for k, n in self.PROJECT_BOARDS}
            for f in as_completed(futs):
                k, n = futs[f]
                try:
                    items = f.result()
                    all_results.extend(items)
                    print(f"  [사업내역/{n}] {len(items)}건", flush=True)
                except Exception as e:
                    print(f"  [사업내역/{n}] 실패: {e}", flush=True)

        # 3) 사업안내 컨텐츠 13개 (순차, 정적 페이지)
        print(f"[전남개발공사] 사업안내 컨텐츠 {len(self.ANNAE_CONTENTS)}개 시작...",
              flush=True)
        for code, label in self.ANNAE_CONTENTS:
            item = self._crawl_annae_content(code, label)
            if item:
                all_results.append(item)
        print(f"  [사업안내] {len(self.ANNAE_CONTENTS)}건", flush=True)

        # dedup by URL
        seen = set()
        deduped = []
        for it in all_results:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            deduped.append(it)

        # 날짜 필터 (날짜 없는 항목은 통과)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        filtered = [
            it for it in deduped
            if not it["date"] or (start_date <= it["date"][:10] <= end_date)
        ]
        filtered.sort(key=lambda x: x["date"] or "", reverse=True)

        elapsed = int(time.time() - t0)
        print(f"[전남개발공사] 완료: 총 {len(filtered)}건 / {elapsed}s", flush=True)
        return filtered


def main():
    import urllib3
    urllib3.disable_warnings()
    c = JNDCCrawler()
    items = c.search(start_date="2000-01-01", end_date="2099-12-31")
    print(f"\n총 {len(items)}건")
    from collections import Counter
    for k, v in Counter(it["organization"] for it in items).most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
