# -*- coding: utf-8 -*-
"""
춘천도시공사 입찰정보(기타) 크롤러
https://www.cuc.or.kr/listBoard.do?divId=155
GET 기반, 10건/페이지
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.cuc.or.kr"
LIST_URL = f"{BASE_URL}/listBoard.do"
PAGE_SIZE = 15


class CUCBidCrawler:
    """춘천도시공사 입찰정보(기타) 크롤러"""

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
            "divId": "155",
            "pageIndex": page,
        }
        if keyword:
            params["searchWord"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 총 건수: "Total 1109"
        total_count = 0
        m = re.search(r'Total\s*(\d[\d,]*)', soup.get_text(), re.IGNORECASE)
        if not m:
            m = re.search(r'총\s*(\d[\d,]*)', soup.get_text())
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        # ul.board-list > li.board-list-box 구조
        for li in soup.select("li.board-list-box"):
            link = li.select_one("a.board-list-lnk")
            if not link:
                continue

            data_id = link.get("data-id", "")
            detail_url = f"{BASE_URL}/viewBoard.do?divId=155&nttId={data_id}" if data_id else ""

            num_el = li.select_one(".board-list-item.num .cont")
            number = num_el.get_text(strip=True) if num_el else ""

            tit_el = li.select_one(".board-list-item.tit .cont")
            title = " ".join(tit_el.get_text().split()) if tit_el else ""

            date_el = li.select_one(".board-list-item.date .cont")
            date = date_el.get_text(strip=True) if date_el else ""

            writer_el = li.select_one(".board-list-item.writer .cont")
            author = " ".join(writer_el.get_text().split()) if writer_el else "춘천도시공사"

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": author,
            })

        return items, total_count

    WORKERS = 5

    def search(self, keyword="", max_pages=10):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE)) if total_count else 1
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
        print(f"[춘천도시공사 입찰] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = CUCBidCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
