# -*- coding: utf-8 -*-
"""
당진도시공사 입찰공고 크롤러
https://www.djuc.or.kr/sub_report/board.php?b_name=BDN_NTC&dp1=report&dp2=bid&dp3=7
GET 기반, 10건/페이지
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.djuc.or.kr"
BOARD_URL = f"{BASE_URL}/sub_report/board.php"


class DJUCCrawler:
    """당진도시공사 입찰공고 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        self.session.verify = False

    def _fetch_page(self, keyword, page):
        """게시판 목록 한 페이지를 가져옵니다."""
        params = {
            "b_name": "BDN_NTC",
            "dp1": "report",
            "dp2": "bid",
            "dp3": "7",
            "page": page,
        }
        if keyword:
            params["keyfield"] = "subject"
            params["key"] = keyword

        resp = self.session.get(BOARD_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 첫 번째 게시글 번호로 총 페이지 수 계산
        total_pages = 1

        # 게시글 파싱
        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_pages

        rows = table.select("tr")[1:]  # 헤더 제외
        for row in rows:
            cells = row.select("td")
            if len(cells) < 4:
                continue

            number = cells[0].get_text(strip=True)
            if page == 1 and number.isdigit() and total_pages == 1:
                total_pages = max(1, math.ceil(int(number) / 10))

            author = cells[2].get_text(strip=True)
            date = cells[3].get_text(strip=True)

            a = cells[1].select_one("a.board_aTit")
            if not a:
                continue

            # span 제거 후 제목 추출
            for span in a.select("span"):
                span.decompose()
            title = " ".join(a.get_text().split())

            href = a.get("href", "")
            detail_url = f"{BASE_URL}{href}" if href.startswith("/") else href

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
        """입찰공고를 검색합니다."""
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
        print(f"[당진도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")

    crawler = DJUCCrawler()
    print("=== 전체 조회 ===")
    results = crawler.search("", max_pages=10)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:55]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=10)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:55]} | {r['organization']}")
