# -*- coding: utf-8 -*-
"""양주도시공사 (yjuc) - xlsx 52행

통합검색 페이지 크롤러.
https://www.yjuc.or.kr/contents/search_result.asp?tsearchOpt1=2&tsearchName=<kw>
- tsearchOpt1=2 : 게시글 본문 통합검색 (게시판 전체)
- 페이지네이션 : fpage=N (10건/페이지, intPageSize 파라미터는 무시됨)
- 빈 키워드는 클라이언트 JS로 차단되므로 다중 키워드 dedup 방식 사용.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup


class YJUCCrawler:
    """양주도시공사 통합검색 크롤러."""

    BASE_URL = "https://www.yjuc.or.kr"
    SEARCH_URL = BASE_URL + "/contents/search_result.asp"

    # '%' 는 사이트 검색 로직상 실질적인 match-all 로 동작 (전 게시판 최고 커버리지).
    KEYWORDS = ["%"]

    MAX_PAGES = 500          # 안전 상한 (실측 455 페이지)
    EMPTY_STOP = 3           # 빈 페이지 연속 N회면 종료
    PAGE_SIZE_HINT = 10      # 서버 고정
    MAX_RETRIES = 4
    WORKERS = 6              # 동시 요청 수 (실측 16 은 throttle 발생)

    # cIdx → 게시판 한글 라벨 (path div 파싱 실패 시 fallback)
    BOARD_LABELS = {
        "board_notice": "안내사항",
        "board_bid": "입찰정보",
        "board_job": "채용안내",
        "board_customer": "고객의소리",
        "board_customer_result": "고객의소리 답변",
        "board_compliment": "칭찬합시다",
        "board_press": "보도자료",
        "board_gallery": "포토갤러리",
        "board_public": "정보공개",
        "board_publc": "정보공개",
        "board_audit": "감사",
        "board_ethics": "윤리경영",
        "board_innovation": "혁신",
        "board_budget": "예산",
        "board_operation": "운영",
        "board_oper_resule": "운영결과",
        "board_report": "보고",
        "board_reward": "포상",
        "board_safe": "안전",
        "board_show": "행사",
        "board_faq": "자주묻는질문",
        "board_newsletter": "뉴스레터",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        adapter = HTTPAdapter(pool_connections=self.WORKERS,
                              pool_maxsize=self.WORKERS * 2)
        self.session.mount("https://", adapter)
        self.session.verify = False

    # ------------------------------------------------------------------ HTTP
    def _fetch(self, keyword: str, page: int):
        params = {
            "tsearchOpt1": 2,
            "tsearchName": keyword,
            "fpage": page,
            "intPageSize": self.PAGE_SIZE_HINT,
        }
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.get(self.SEARCH_URL, params=params, timeout=30)
                r.raise_for_status()
                r.encoding = "utf-8"
                return BeautifulSoup(r.text, "lxml")
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.2 * (attempt + 1))
        return None

    # ------------------------------------------------------------------ Parse
    def _parse_item(self, li) -> dict | None:
        a = li.select_one("h5.sh_tit1 a, h5 a")
        if not a:
            return None
        href = a.get("href", "") or ""
        m_num = re.search(r"num=(\d+)", href)
        m_fb = re.search(r"fboard=([A-Za-z_]+)", href)
        m_cidx = re.search(r"cIdx=(\d+)", href)
        if not m_num or not m_fb:
            return None
        num = m_num.group(1)
        fboard = m_fb.group(1)
        cidx = m_cidx.group(1) if m_cidx else ""

        title = a.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) < 2:
            return None

        # 날짜 : <span class="date">YYYY-MM-DD</span>
        date = ""
        d = li.select_one("span.date")
        if d:
            t = d.get_text(" ", strip=True)
            m2 = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", t)
            if m2:
                date = f"{m2.group(1)}-{m2.group(2).zfill(2)}-{m2.group(3).zfill(2)}"

        # 게시판 라벨 : path div 텍스트의 마지막 세그먼트
        board_label = self.BOARD_LABELS.get(fboard, fboard)
        path = li.select_one("div.path a")
        if path:
            txt = re.sub(r"\s+", " ", path.get_text(" ", strip=True))
            # "알림마당 > 홍보자료 > 보도자료" → "보도자료"
            segs = [s.strip() for s in txt.split(">") if s.strip()]
            if segs:
                board_label = segs[-1]

        url = f"{self.BASE_URL}/sub/content.asp?cIdx={cidx}&fboard={fboard}&num={num}&actionMode=view"
        return {
            "title": title,
            "date": date,
            "url": url,
            "organization": board_label,
            "number": num,
            "_dedup_key": f"{fboard}_{num}",
        }

    # ------------------------------------------------------------------ Crawl
    def _fetch_and_parse(self, keyword: str, page: int):
        soup = self._fetch(keyword, page)
        if soup is None:
            return page, []
        res = soup.select_one("div.result")
        items = res.select("li") if res else []
        parsed = []
        for li in items:
            it = self._parse_item(li)
            if it:
                parsed.append(it)
        return page, parsed

    def _crawl_keyword(self, keyword: str, collected: dict, verbose: bool = True):
        """배치 단위 병렬 요청. 배치 내 items 가 0 이면 종료."""
        added = 0
        page = 1
        BATCH = self.WORKERS * 3   # 24 pages per batch
        t0 = time.time()
        while page <= self.MAX_PAGES:
            batch_pages = list(range(page, min(page + BATCH, self.MAX_PAGES + 1)))
            results = {}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as ex:
                futures = [ex.submit(self._fetch_and_parse, keyword, p) for p in batch_pages]
                for fut in as_completed(futures):
                    try:
                        p, items = fut.result()
                        results[p] = items
                    except Exception:
                        pass

            batch_added = 0
            batch_items_total = 0
            for p in batch_pages:
                items = results.get(p, [])
                batch_items_total += len(items)
                for it in items:
                    key = it.pop("_dedup_key")
                    if key in collected:
                        continue
                    collected[key] = it
                    added += 1
                    batch_added += 1

            if verbose:
                print(f"    [{keyword}] p{batch_pages[0]}-{batch_pages[-1]}: "
                      f"+{batch_added} items={batch_items_total} total={len(collected)} "
                      f"({time.time()-t0:.0f}s)", flush=True)

            # 배치 items 가 0이면 데이터 끝, 종료
            if batch_items_total == 0:
                break

            page += BATCH
        return added

    # ------------------------------------------------------------------ Public
    def search(self, keyword: str = "", max_pages: int = 999,
               start_date: str | None = None, end_date: str | None = None):
        collected: dict[str, dict] = {}
        for i, kw in enumerate(self.KEYWORDS, 1):
            t0 = time.time()
            try:
                added = self._crawl_keyword(kw, collected)
                print(f"  [{i}/{len(self.KEYWORDS)}] '{kw}' +{added} → {len(collected)}건 "
                      f"({time.time() - t0:.0f}s)", flush=True)
            except Exception as e:
                print(f"  [{i}/{len(self.KEYWORDS)}] '{kw}' 에러: {str(e)[:60]}", flush=True)
            time.sleep(0.2)

        items = list(collected.values())

        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        items = [it for it in items
                 if not it["date"] or (start_date <= it["date"][:10] <= end_date)]
        items.sort(key=lambda x: x["date"] or "", reverse=True)
        print(f"[양주도시공사] 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    import urllib3
    urllib3.disable_warnings()
    c = YJUCCrawler()
    t0 = time.time()
    items = c.search(start_date="2000-01-01", end_date="2099-12-31")
    print(f"{len(items)}건 / {time.time() - t0:.0f}초")
    from collections import Counter
    for k, v in Counter(it["organization"] for it in items).most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
