# -*- coding: utf-8 -*-
"""
전북특별자치도청 타기관공고 크롤러
https://www.jeonbuk.go.kr/board/list.jeonbuk?boardId=BBS_0000006&menuCd=DOM_000000102002006000
GET 기반, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.jeonbuk.go.kr"
LIST_URL = f"{BASE_URL}/board/list.jeonbuk"
PAGE_SIZE = 100


class JeonbukOtherCrawler:
    """전북특별자치도청 타기관공고 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _fetch_page(self, keyword, page):
        params = {
            "boardId": "BBS_0000006",
            "menuCd": "DOM_000000102002006000",
            "listCel": "1",
            "listRow": PAGE_SIZE,
            "paging": "ok",
            "searchType": "DATA_TITLE",
            "startPage": page,
        }
        if keyword:
            params["keyword"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: "총 21448건(1/2145 페이지)"
        total_count = 0
        total_el = soup.select_one("p.bbs_total")
        if total_el:
            m = re.search(r'총\s*(\d[\d,]*)\s*건', total_el.get_text())
            if m:
                total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table.bbs_table")
        if not table:
            return items, total_count

        # 컬럼: 번호, 제목, 첨부, 작성자, 작성일, 조회
        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            # 첨부(2), 작성자(3), 작성일(4), 조회(5)
            author = cells[3].get_text(strip=True) if len(cells) >= 5 else "전북특별자치도청"
            date = cells[4].get_text(strip=True) if len(cells) >= 6 else cells[-2].get_text(strip=True)

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "전북특별자치도청",
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
        print(f"[전북특별자치도청 타기관공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = JeonbukOtherCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
