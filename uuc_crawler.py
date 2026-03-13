# -*- coding: utf-8 -*-
"""
의왕도시공사 통합검색 크롤러
https://www.uuc.or.kr/base/search/view?searchType=BOARD
GET 기반, 게시판 검색
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.uuc.or.kr"
SEARCH_URL = f"{BASE_URL}/base/search/view"
PAGE_SIZE = 10


class UUCCrawler:
    """의왕도시공사 통합검색 크롤러"""

    WORKERS = 5

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
        params = {
            "searchType": "BOARD",
            "searchWord": keyword,
            "page": page,
        }
        resp = self.session.get(SEARCH_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        total_count = 0
        for a in soup.select("a"):
            text = a.get_text()
            m = re.search(r'게시판\s*\(\s*(\d[\d,]*)\s*\)', text)
            if m:
                total_count = int(m.group(1).replace(",", ""))
                break

        items = []
        result_list = soup.select(".sch_result_page_list li")
        for li in result_list:
            title_a = li.select_one("p.tit a, a")
            if not title_a:
                continue

            title = title_a.get_text(strip=True)
            href = title_a.get("href", "")
            detail_url = f"{BASE_URL}{href}" if href.startswith("/") else href

            date = ""
            m2 = re.search(r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})', li.get_text())
            if m2:
                date = m2.group(1)

            items.append({
                "number": "",
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "의왕도시공사",
            })

        return items, total_count

    def search(self, keyword="", max_pages=10):
        if not keyword:
            print("[의왕도시공사] 통합검색은 키워드가 필요합니다")
            return []

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

        print(f"[의왕도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    crawler = UUCCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
