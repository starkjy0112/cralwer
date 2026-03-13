# -*- coding: utf-8 -*-
"""
평택도시공사 입찰정보 크롤러
https://www.puc.or.kr/noticeInfo/noticeInfoList.do
POST 기반, t_type=t_4 (입찰정보), 10건/페이지
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.puc.or.kr"
LIST_URL = f"{BASE_URL}/noticeInfo/noticeInfoList.do"
PAGE_SIZE = 10


class PUCCrawler:
    """평택도시공사 입찰정보 크롤러"""

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
        data = {
            "t_type": "t_4",
            "Tname": "Notice",
            "page": page,
            "rowCount": PAGE_SIZE,
        }
        if keyword:
            data["searchstring"] = keyword

        resp = self.session.post(LIST_URL, data=data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        total_count = 0
        tr_input = soup.select_one("input[name=TotalRecord]")
        if tr_input:
            try:
                total_count = int(tr_input.get("value", "0"))
            except ValueError:
                pass

        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tr")[1:]
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            author = cells[2].get_text(strip=True)
            date = cells[3].get_text(strip=True)

            link = title_cell.select_one("a")
            title = ""
            detail_url = ""
            if link:
                title = link.get_text(strip=True)
                onclick = link.get("onclick", "")
                m2 = re.search(r"goViewPage\('([^']+)'\)", onclick)
                if m2:
                    idx = m2.group(1)
                    detail_url = f"{BASE_URL}/noticeInfo/noticeInfoView.do?idx={idx}"

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "평택도시공사",
            })

        return items, total_count

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
        print(f"[평택도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = PUCCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=50)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
