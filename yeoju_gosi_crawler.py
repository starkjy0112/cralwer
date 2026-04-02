# -*- coding: utf-8 -*-
"""
여주시청 고시·공고·입법예고 크롤러
https://www.yeoju.go.kr/www/selectEminwonList.do?key=413
GET 기반, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.yeoju.go.kr"
LIST_URL = f"{BASE_URL}/www/selectEminwonList.do"
PAGE_SIZE = 100


class YeojuGosiCrawler:
    """여주시청 고시·공고·입법예고 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.verify = False

    def _fetch_page(self, keyword, page):
        params = {
            "key": "413",
            "pageIndex": str(page),
            "pageUnit": str(PAGE_SIZE),
        }
        if keyword:
            params["searchCnd"] = "B_Subject"
            params["searchKrwd"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 2154건
        total_count = 0
        m = re.search(r'총\s*([\d,]+)\s*건', resp.text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table.p-table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 5:
                continue

            number = tds[0].get_text(strip=True)

            if total_count == 0 and page == 1 and number.isdigit():
                total_count = int(number)

            notice_no = tds[1].get_text(strip=True)

            title_td = tds[2]
            link = title_td.find("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("./"):
                detail_url = f"{BASE_URL}/www/{href[2:]}"
            elif href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            dept = tds[3].get_text(strip=True)
            date = tds[4].get_text(strip=True)

            items.append({
                "number": number,
                "title": f"[{notice_no}] {title}" if notice_no else title,
                "date": date,
                "url": detail_url,
                "organization": "여주시청",
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
        print(f"[여주시청 고시·공고·입법예고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    crawler = YeojuGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
