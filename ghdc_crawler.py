# -*- coding: utf-8 -*-
"""
김해시도시개발공사 크롤러
xlsx 24행: 통합검색 URL을 진입점으로 사용

통합검색(code=08_05)은 페이지당 31건만 노출되고 페이지네이션이 없어
'다중 키워드 검색 → 등장 게시판 자동 발견 → 각 게시판 리스트 순회'로
모든 게시글을 수집한다.

- 통합검색: 다중 키워드로 등장 board code 자동 수집 (SEARCH_KEYWORDS)
- 게시판 리스트: mode=list&page=N 순회 (날짜 포함)
- URL 기준 dedup
"""
import re
import time
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


class GhdcCrawler:
    """김해시도시개발공사 크롤러"""

    BASE_URL = "https://ghdc.or.kr"
    SUB_URL = f"{BASE_URL}/sub.html"
    SEARCH_CODE = "08_05"

    # xlsx 지정 25개 기술 키워드 + 광범위 커버리지 16개 = 총 41개
    SEARCH_KEYWORDS = [
        # xlsx ① 기술 키워드 (특허/신기술 관련 - 25개)
        "기본설계", "실시설계", "기술제안", "제안서", "신기술", "공법", "특허", "특정",
        "발파", "암발파", "미진동", "무진동", "암절취", "흙깍기", "절토", "토공",
        "토목", "토건", "제출", "제안", "부지조성", "단지조성", "산업단지",
        "조성공사", "개발사업",
        # 광범위 커버리지 (16개)
        "공사", "용역", "공고", "입찰", "계약", "분양", "고시",
        "2026", "2025", "2024",
        "가", "이", "리", "수", "동", "시",
    ]

    # 사전 등록된 board (다중검색으로 발견 못 할 경우 기본값)
    KNOWN_BOARDS = {
        "03_01": "공지사항",
        "03_03": "채용정보",
        "04_02": "보도자료",
        "05_03_01": "정보공개",
    }

    WORKERS = 6
    MAX_RETRIES = 3

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ko-KR,ko;q=0.9",
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    # ------- 통합검색: board code 자동 발견 -------
    def _fetch_search(self, keyword):
        params = {
            "code": self.SEARCH_CODE,
            "Radd": self.SEARCH_CODE,
            "keyword": keyword,
        }
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self.session.get(self.SUB_URL, params=params, timeout=30, verify=False)
                resp.raise_for_status()
                resp.encoding = "utf-8"
                return BeautifulSoup(resp.text, "lxml")
            except requests.RequestException:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1)
        return None

    def _discover_boards(self):
        """다중 키워드 검색으로 등장 board code + 이름 사전 구축"""
        boards = dict(self.KNOWN_BOARDS)  # start with known
        for kw in self.SEARCH_KEYWORDS:
            soup = self._fetch_search(kw)
            if not soup:
                continue
            for h3 in soup.select("h3"):
                if "게시글" not in h3.get_text():
                    continue
                dl = h3.find_next_sibling("dl")
                if not dl:
                    continue
                for dt in dl.select("dt"):
                    a = dt.select_one("a")
                    if not a:
                        continue
                    href = a.get("href", "")
                    m = re.search(r"code=([\w_]+)", href)
                    if not m:
                        continue
                    code = m.group(1)
                    txt = a.get_text(strip=True)
                    name = None
                    if " | " in txt:
                        name = txt.split(" | ")[0].strip()
                    if code not in boards and name:
                        boards[code] = name
                break
        return boards

    # ------- 게시판 리스트 순회 -------
    def _fetch_board_page(self, code, page):
        params = {
            "code": code,
            "Radd": code,
            "mode": "list",
            "page": str(page),
        }
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self.session.get(self.SUB_URL, params=params, timeout=30, verify=False)
                resp.raise_for_status()
                resp.encoding = "utf-8"
                return BeautifulSoup(resp.text, "lxml")
            except requests.RequestException:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1)
        return None

    @staticmethod
    def _normalize_date(s):
        if not s:
            return ""
        s = s.strip()
        m = re.match(r"^(\d{4})[-./](\d{1,2})[-./](\d{1,2})$", s)
        if m:
            return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        # 2자리 연도 (YY-MM-DD)
        m = re.match(r"^(\d{2})-(\d{2})-(\d{2})$", s)
        if m:
            y = int(m.group(1))
            year = 2000 + y if y < 70 else 1900 + y
            return f"{year}-{m.group(2)}-{m.group(3)}"
        # HH:MM 형태만 → 오늘 (제목의 'RE:'와 구분)
        if re.match(r"^\d{1,2}:\d{2}$", s):
            return datetime.now().strftime("%Y-%m-%d")
        return ""

    def _parse_board_rows(self, soup, board_code, board_name):
        results = []
        if not soup:
            return results
        for tr in soup.select("tbody tr"):
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue
            # 제목 셀 (a 태그가 있는 첫 번째 td)
            a = tr.select_one("td a")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if href.startswith("/"):
                url = f"{self.BASE_URL}{href}"
            elif href.startswith("http"):
                url = href
            else:
                url = f"{self.BASE_URL}/{href}"
            # 날짜: YYYY/MM/DD 또는 YYYY-MM-DD 패턴을 각 셀에서 찾기
            date = ""
            for td in tds:
                cand = td.get_text(strip=True)
                nd = self._normalize_date(cand)
                if nd and re.match(r"\d{4}-\d{2}-\d{2}", nd):
                    date = nd
                    break
            number = tds[0].get_text(strip=True) if tds[0].get_text(strip=True).isdigit() else ""
            results.append({
                "number": number,
                "title": title,
                "date": date,
                "url": url,
                "organization": board_name,
            })
        return results

    def _crawl_board(self, code, name, max_pages=500):
        """단일 게시판 전체 페이지 순회"""
        results = []
        seen = set()
        page = 1
        empty_streak = 0
        while page <= max_pages:
            soup = self._fetch_board_page(code, page)
            items = self._parse_board_rows(soup, code, name)
            new = [it for it in items if it["url"] not in seen]
            if not new:
                empty_streak += 1
                if empty_streak >= 2:
                    break
                page += 1
                continue
            empty_streak = 0
            for it in new:
                seen.add(it["url"])
                results.append(it)
            page += 1
        return results

    def search(self, keyword="", max_pages=999, start_date=None, end_date=None):
        """통합검색 진입점 → board 자동 발견 → 각 board 전체 순회"""
        # 1) board 자동 발견 (통합검색 URL 기반)
        boards = self._discover_boards()

        # 2) 병렬로 각 board 크롤
        all_results = {}
        with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
            futures = {
                executor.submit(self._crawl_board, code, name): (code, name)
                for code, name in boards.items()
            }
            for future in as_completed(futures):
                code, name = futures[future]
                try:
                    for r in future.result():
                        if r["url"] not in all_results:
                            all_results[r["url"]] = r
                except Exception as e:
                    print(f"  ! board {code} ({name}) 실패: {e}")

        results = list(all_results.values())

        # 3) 날짜 필터
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        results = [
            r for r in results
            if not r["date"] or (start_date <= r["date"][:10] <= end_date)
        ]
        results.sort(key=lambda x: x["date"] or "", reverse=True)
        print(f"[김해시도시개발공사] 완료: 총 {len(results)}건 ({len(boards)}개 게시판)")
        return results


def main():
    import urllib3
    urllib3.disable_warnings()
    c = GhdcCrawler()
    t0 = time.time()
    items = c.search(start_date="2000-01-01", end_date="2099-12-31")
    print(f"{len(items)}건 / {time.time() - t0:.0f}초")
    for r in items[:5]:
        print(f"  [{r['date']}] [{r['organization']}] {r['title'][:60]}")


if __name__ == "__main__":
    main()
