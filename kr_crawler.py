# -*- coding: utf-8 -*-
"""
국가철도공단 공지사항 크롤러
https://www.kr.or.kr/boardCnts/list.do?boardID=51
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.kr.or.kr"
BOARD_ID = "51"


class KRCrawler:
    """국가철도공단 공지사항 크롤러"""

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
            "boardID": BOARD_ID,
            "searchType": "S",  # 제목 검색
            "searchStr": keyword,
            "page": page,
        }
        response = self.session.get(
            f"{BASE_URL}/boardCnts/list.do",
            params=params,
            timeout=15,
        )
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        # 총 페이지 수 추출
        total_pages = 1
        page_links = soup.select("a[href*='boardID='][href*='page=']")
        for link in page_links:
            href = link.get("href", "")
            if "page=" in href:
                try:
                    p = int(href.split("page=")[-1].split("&")[0])
                    if p > total_pages:
                        total_pages = p
                except ValueError:
                    pass

        # 게시글 파싱
        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_pages

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            link = cells[1].select_one("a")
            if not link:
                continue

            number = cells[0].get_text(strip=True)
            title = cells[1].get_text(strip=True)
            author = cells[2].get_text(strip=True)
            date = cells[4].get_text(strip=True)

            href = link.get("href", "")
            if href and not href.startswith("http"):
                detail_url = f"{BASE_URL}/boardCnts/{href}"
            else:
                detail_url = href

            items.append({
                "number": number,
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
        print(f"[국가철도공단] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = KRCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 (2페이지) ===")
    results2 = crawler.search("공고", max_pages=2)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
