# -*- coding: utf-8 -*-
"""
동대문구청 고시공고 크롤러
https://www.ddm.go.kr/www/selectEminwonWebList.do?key=3291&searchNotAncmtSeCode=01,02,04,05,06,07
GET 기반, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.ddm.go.kr"
LIST_URL = f"{BASE_URL}/www/selectEminwonWebList.do"
DETAIL_URL = f"{BASE_URL}/www/selectEminwonWebView.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "동대문구청"
KEY = "3291"
SE_CODE = "01,02,04,05,06,07"


class DdmGosiCrawler:
    """동대문구청 고시공고 크롤러"""

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
        params = {
            "key": KEY,
            "searchNotAncmtSeCode": SE_CODE,
            "pageIndex": str(page),
            "pageUnit": str(PAGE_SIZE),
        }
        if keyword:
            params["searchCnd"] = "notAncmtSj"
            params["searchKrwd"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0

        items = []
        table = soup.find("table", class_=lambda c: c and "p-table" in str(c))
        if not table:
            for t in soup.find_all("table"):
                rows = t.find_all("tr")
                if len(rows) > 3:
                    table = t
                    break

        if table:
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 4:
                    continue
                # 번호, 고시공고번호, 진행사항, 고시공고명, 담당부서, 공고시작일, 공고종료일
                number = tds[0].get_text(strip=True).replace(",", "")
                if not total_count and number.isdigit():
                    total_count = int(number)

                title_td = tds[3]
                title_tag = title_td.find("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                if href.startswith("./"):
                    detail_url = BASE_URL + "/www/" + href[2:]
                elif href and not href.startswith("http"):
                    detail_url = BASE_URL + href
                else:
                    detail_url = href

                # 공고시작일
                date = tds[5].get_text(strip=True) if len(tds) > 5 else ""

                items.append({
                    "number": number,
                    "title": title,
                    "date": date,
                    "url": detail_url,
                    "organization": ORGANIZATION_NAME,
                })

        # 페이지네이션 추정
        if not total_count:
            paging = soup.find("div", class_="p-pagination")
            if paging:
                max_page = 1
                for a in paging.find_all("a"):
                    href = a.get("href", "")
                    m_p = re.search(r"pageIndex=(\d+)", href)
                    if m_p:
                        pn = int(m_p.group(1))
                        if pn > max_page:
                            max_page = pn
                total_count = max_page * PAGE_SIZE

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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = DdmGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
