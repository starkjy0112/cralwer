# -*- coding: utf-8 -*-
"""
충청남도개발공사 입찰공고 크롤러
https://www.cndc.kr/bbs/list.do?key=2404080009
"""
import math
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.cndc.kr"
BOARD_KEY = "2404080009"


class CNDCCrawler:
    """충청남도개발공사 입찰공고 크롤러"""

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
            "key": BOARD_KEY,
            "pageIndex": page,
            "orderBy": "bbsOrdr desc",
        }
        if keyword:
            params["sc"] = "pstTtl"  # 제목 검색
            params["sw"] = keyword

        response = self.session.get(
            f"{BASE_URL}/bbs/list.do",
            params=params,
            timeout=15,
        )
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        # 총 페이지 수 - 전체 X 중 페이지 X / XX 형태 파싱
        total_pages = 1
        import re
        page_text = soup.get_text()
        match = re.search(r'전체\s*(\d+)', page_text)
        if match:
            total_count = int(match.group(1))
            total_pages = max(1, math.ceil(total_count / 10))

        # 게시글 파싱
        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_pages

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 6:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            dept = cells[3].get_text(strip=True)
            date = cells[5].get_text(strip=True)

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)

            # onclick에서 ID 추출: goView('26024358')
            onclick = link.get("onclick", "")
            pst_sn = ""
            match = re.search(r"goView\('(\d+)'\)", onclick)
            if match:
                pst_sn = match.group(1)
            detail_url = f"{BASE_URL}/bbs/view.do?key={BOARD_KEY}&pstSn={pst_sn}" if pst_sn else ""

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": dept,
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
        print(f"[충남개발공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = CNDCCrawler()
    print("=== 전체 조회 (2페이지) ===")
    results = crawler.search("", max_pages=2)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 (2페이지) ===")
    results2 = crawler.search("공고", max_pages=2)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
