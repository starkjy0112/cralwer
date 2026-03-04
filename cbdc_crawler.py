# -*- coding: utf-8 -*-
"""
충북개발공사 공지사항 크롤러
https://www.cbdc.co.kr/zboard/list.do?lmCode=BBSMSTR_000000000018
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.cbdc.co.kr"
LM_CODE = "BBSMSTR_000000000018"


class CBDCCrawler:
    """충북개발공사 공지사항 크롤러"""

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
            "lmCode": LM_CODE,
            "searchCnd": "0",  # 제목+내용
            "searchWrd": keyword,
            "pageIndex": page,
        }
        response = self.session.get(
            f"{BASE_URL}/zboard/list.do",
            params=params,
            timeout=15,
        )
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        # 총 게시물 수 파싱
        total_count = 0
        total_text = soup.get_text()
        match = re.search(r'총[^0-9]*(\d+)', total_text)
        if match:
            total_count = int(match.group(1))
        total_pages = max(1, math.ceil(total_count / 15))

        # 게시글 파싱
        items = []
        table = soup.select_one("table.board-list-table")
        if not table:
            return items, total_pages

        rows = table.select("tr")
        for row in rows[1:]:  # 헤더 제외
            cells = row.select("td")
            if len(cells) < 6:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            author = cells[2].get_text(strip=True)
            date = cells[4].get_text(strip=True)

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            detail_url = f"{BASE_URL}{href}" if href.startswith("/") else href

            items.append({
                "number": number.replace("[공지]", "공지").strip(),
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": author,
            })

        return items, total_pages

    WORKERS = 5

    def search(self, keyword="", max_pages=10):
        """공지사항을 검색합니다."""
        first_items, total_pages = self._fetch_page(keyword, 1)
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집")

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
        print(f"[충북개발공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = CBDCCrawler()
    print("=== 전체 조회 (2페이지) ===")
    results = crawler.search("", max_pages=2)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 (2페이지) ===")
    results2 = crawler.search("공고", max_pages=2)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
