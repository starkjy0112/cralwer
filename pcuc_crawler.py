# -*- coding: utf-8 -*-
"""
포천도시공사 게시판검색 크롤러
https://www.pcuc.kr/open_content/searchBbs.do
GET 기반
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.pcuc.kr"
SEARCH_URL = f"{BASE_URL}/open_content/searchBbs.do"
PAGE_SIZE = 10


class PCUCCrawler:
    """포천도시공사 게시판검색 크롤러"""

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

    def _fetch_page(self, keyword, page):
        params = {
            "keyword": keyword,
            "pgno": page,
        }
        resp = self.session.get(SEARCH_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        total_count = 0
        m = re.search(r'(\d[\d,]*)\s*건', soup.get_text())
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        for dl in soup.find_all("dl"):
            link = dl.select_one("dt a, a")
            if not link:
                continue

            title = link.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            href = link.get("href", "")
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            date = ""
            dds = dl.find_all("dd")
            for dd in dds:
                m2 = re.search(r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})', dd.get_text())
                if m2:
                    date = m2.group(1)
                    break

            items.append({
                "number": "",
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "포천도시공사",
            })

        return items, total_count

    def search(self, keyword="", max_pages=10):
        if not keyword:
            print("[포천도시공사] 게시판검색은 키워드가 필요합니다")
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

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[포천도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = PCUCCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
