# -*- coding: utf-8 -*-
"""
경상남도청 고시공고 크롤러
https://www.gyeongnam.go.kr/index.gyeong?menuCd=DOM_000000135003009001
GET 기반 (index.gyeong), 10건/페이지
초기 접속 후 세션 유지 필요, 서버 측 날짜 필터 기본 적용됨
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gyeongnam.go.kr"
LIST_URL = f"{BASE_URL}/index.gyeong"
MENU_CD = "DOM_000000135003009001"
PAGE_SIZE = 100


class GSNDGosiCrawler:
    """경상남도청 고시공고 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        # 초기 접속으로 세션/쿠키 확보
        self.session.get(f"{LIST_URL}?menuCd={MENU_CD}", timeout=15)

    def _fetch_page(self, keyword, page):
        params = {
            "menuCd": MENU_CD,
            "pageLine": str(PAGE_SIZE),
            "page": str(page),
        }
        if keyword:
            params["conTitle"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 총 건수: 검색건수 :<span class="count-1">510</span>건
        total_count = 0
        count_span = soup.select_one("span.count-1")
        if count_span:
            total_count = int(count_span.get_text(strip=True).replace(",", ""))

        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            # 컬럼: 구분, 고시/공고 번호, 제목, 의뢰부서, 게재일시
            number = cells[1].get_text(strip=True)
            title_cell = cells[2]
            dept = cells[3].get_text(strip=True)
            date = cells[4].get_text(strip=True)

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": dept if dept else "경상남도청",
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        if actual_pages <= 1:
            all_items = first_items
        else:
            page_results = {1: first_items}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_page, keyword, p): p
                    for p in range(2, actual_pages + 1)
                }
                for future in as_completed(futures):
                    p = futures[future]
                    try:
                        items, _ = future.result()
                        if items:
                            page_results[p] = items
                    except Exception:
                        pass

            all_items = []
            for p in sorted(page_results.keys()):
                all_items.extend(page_results[p])

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[경상남도청 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GSNDGosiCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
