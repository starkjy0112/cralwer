# -*- coding: utf-8 -*-
"""
함양군청 고시/공고 크롤러
https://www.hygn.go.kr/00429/00543/00549.web
iframe → eminwon.hygn.go.kr POST 기반, table, 10건/페이지, pageIndex 파라미터
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://eminwon.hygn.go.kr"
ACTION_URL = f"{BASE_URL}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
VIEW_URL = "https://www.hygn.go.kr/00429/00543/00549.web"
PAGE_SIZE = 10
ORGANIZATION_NAME = "함양군청"


class HamyangCrawler:
    """함양군청 고시/공고 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
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

    def _fetch_page(self, keyword, page):
        data = {
            "pageIndex": str(page),
            "jndinm": "OfrNotAncmtEJB",
            "context": "NTIS",
            "method": "selectListOfrNotAncmt",
            "methodnm": "selectListOfrNotAncmtHomepage",
            "homepage_pbs_yn": "Y",
            "subCheck": "Y",
            "ofr_pageSize": str(PAGE_SIZE),
            "not_ancmt_se_code": "01",
            "title": "고시",
            "countYn": "Y",
            "not_ancmt_sj": keyword if keyword else "",
        }

        resp = self.session.post(ACTION_URL, data=data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []

        text = soup.get_text()
        m = re.search(r"총\s*(\d[\d,]*)\s*건", text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        for table in soup.select("table"):
            tbody = table.find("tbody")
            if not tbody:
                continue
            rows = tbody.find_all("tr")
            if not rows:
                continue
            first_tds = rows[0].find_all("td")
            if len(first_tds) < 5:
                continue

            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 6:
                    continue

                number = tds[0].get_text(strip=True)
                gosi_no = tds[1].get_text(strip=True)
                a_tag = tds[2].find("a")
                if a_tag:
                    title = a_tag.get_text(strip=True)
                else:
                    title = tds[2].get_text(strip=True)

                dept = tds[3].get_text(strip=True)
                date_str = tds[4].get_text(strip=True).replace(".", "-")

                items.append({
                    "number": gosi_no if gosi_no else number,
                    "title": title,
                    "date": date_str,
                    "url": VIEW_URL,
                    "organization": ORGANIZATION_NAME,
                })

            break

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
        print(f"[{ORGANIZATION_NAME} 고시/공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = HamyangCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n=== '용역' 검색 ===")
    results2 = crawler.search("용역", max_pages=1)
    for r in results2[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n공고: {len(results)}건, 용역: {len(results2)}건")
