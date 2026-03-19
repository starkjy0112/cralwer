# -*- coding: utf-8 -*-
"""
대전광역시청 대전소식모아보기 크롤러
https://www.daejeon.go.kr/drh/MediaList.do?notiType=&menuSeq=2558
GET 기반, 10건/페이지
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.daejeon.go.kr"
LIST_URL = f"{BASE_URL}/drh/MediaList.do"
PAGE_SIZE = 10


class DaejeonAllCrawler:
    """대전광역시청 대전소식모아보기 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    def _fetch_page(self, keyword, page):
        params = {
            "menuSeq": "2558",
            "notiType": "",
            "pageIndex": page,
        }
        if keyword:
            params["searchKeyword"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 총 건수: "총 24729건"
        total_count = 0
        counter = soup.select_one("p.total_counter")
        if counter:
            m = re.search(r'총\s*(\d[\d,]*)\s*건', counter.get_text())
            if m:
                total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table.board_table_list")
        if not table:
            return items, total_count

        rows = table.select("tbody tr") or table.select("tr")[1:]
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            org = cells[1].get_text(strip=True)       # 기관
            category = cells[2].get_text(strip=True)   # 분류
            title_cell = cells[3]
            date = cells[4].get_text(strip=True)

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            elif href.startswith("http"):
                detail_url = href
            else:
                detail_url = href

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "대전광역시청",
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
        print(f"[대전광역시청 전체] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = DaejeonAllCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '입찰' 검색 ===")
    results2 = crawler.search("입찰", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
