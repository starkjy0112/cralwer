# -*- coding: utf-8 -*-
"""
군포도시공사 입찰공고 크롤러
https://www.gunpouc.or.kr/fmcs/90
GET 기반, page_size=20
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gunpouc.or.kr"
BOARD_PATH = "/fmcs/90"
PAGE_SIZE = 20


class GUNPOUCCrawler:
    """군포도시공사 입찰공고 크롤러"""

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
        """게시판 목록 한 페이지를 가져옵니다."""
        params = {
            "page": page,
            "page_size": PAGE_SIZE,
            "search_field": "Ti",
            "search_word": keyword,
        }
        resp = self.session.get(
            f"{BASE_URL}{BOARD_PATH}",
            params=params,
            timeout=15,
        )
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 총 건수: "546건의 게시물이 등록되어 있습니다" 또는 "546건"
        total_count = 0
        m = re.search(r'(\d+)\s*건', soup.get_text())
        if m:
            total_count = int(m.group(1))

        # 게시글 파싱
        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tr")[1:]  # 헤더 제외
        for row in rows:
            cells = row.select("td")
            if len(cells) < 3:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            date = cells[-1].get_text(strip=True)

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            detail_url = f"{BASE_URL}{BOARD_PATH}{href}" if href.startswith("?") else href

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "군포도시공사",
            })

        return items, total_count

    WORKERS = 5

    def search(self, keyword="", max_pages=10):
        """입찰공고를 검색합니다."""
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
        print(f"[군포도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GUNPOUCCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")

    print("\n=== '공고' 검색 (3페이지) ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
