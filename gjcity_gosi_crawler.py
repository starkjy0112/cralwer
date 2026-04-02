# -*- coding: utf-8 -*-
"""
광주시청 고시공고 크롤러
https://www.gjcity.go.kr/portal/saeol/gosi/list.do?mId=0202010000
POST 기반, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gjcity.go.kr"
LIST_URL = f"{BASE_URL}/portal/saeol/gosi/list.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "광주시청"


class GjcityGosiCrawler:
    """광주시청 고시공고 크롤러"""

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
            "mId": "0202010000",
            "page": str(page),
            "seCode": "01",
        }
        if keyword:
            data["searchType"] = "title"
            data["searchTxt"] = keyword

        resp = self.session.post(LIST_URL, data=data, params={"mId": "0202010000"}, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # Parse total pages from "현재 페이지 1 / 전체 페이지 1103"
        total_count = 0
        page_num = soup.find("p", class_="page_num") or soup.find("span", class_="page_num")
        if page_num:
            m = re.search(r"전체\s*페이지\s*(\d+)", page_num.get_text())
            if m:
                total_count = int(m.group(1)) * PAGE_SIZE

        items = []
        table = soup.find("table", class_="bod_list")
        if table:
            tbody = table.find("tbody")
            if tbody:
                for tr in tbody.find_all("tr"):
                    tds = tr.find_all("td")
                    if len(tds) < 5:
                        continue
                    # 번호, 고시공고번호, 제목, 담당부서, 등록일
                    number = tds[0].get_text(strip=True)
                    title_td = tds[2]
                    title_tag = title_td.find("a")
                    if not title_tag:
                        continue
                    # Remove "새 글" icon text
                    for ico in title_tag.find_all("span", class_="ico_new"):
                        ico.decompose()
                    title = title_tag.get_text(strip=True)
                    data_action = title_tag.get("data-action", "")
                    detail_url = BASE_URL + data_action if data_action else ""
                    date = tds[4].get_text(strip=True)

                    items.append({
                        "number": number,
                        "title": title,
                        "date": date,
                        "url": detail_url,
                        "organization": ORGANIZATION_NAME,
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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GjcityGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
