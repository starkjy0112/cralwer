# -*- coding: utf-8 -*-
"""
구미시청 고시공고 크롤러
https://www.gumi.go.kr/portal/saeol/gosi/list.do?seCode=01&mid=0401040000
POST 기반, table.bod_list, 10건/페이지, page_num 페이지네이션
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gumi.go.kr"
LIST_URL = f"{BASE_URL}/portal/saeol/gosi/list.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "구미시청"


class GumiGosiCrawler:
    """구미시청 고시공고 크롤러"""

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
            "page": str(page),
            "pageSize": "10",
            "seCode": "01",
        }
        if keyword:
            data["searchType"] = "tit"
            data["searchTxt"] = keyword

        resp = self.session.post(
            f"{LIST_URL}?seCode=01&mid=0401040000", data=data, timeout=15
        )
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # Parse total pages from "현재 페이지1/ 전체 페이지 1,743"
        total_count = 0
        page_num = soup.find("p", class_="page_num") or soup.find("span", class_="page_num")
        if page_num:
            m = re.search(r"전체\s*페이지\s*([\d,]+)", page_num.get_text())
            if m:
                total_count = int(m.group(1).replace(",", "")) * PAGE_SIZE

        items = []
        table = soup.find("table", class_="bod_list") or soup.find("table")
        if not table:
            return items, total_count

        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            number = tds[0].get_text(strip=True)
            gosi_no = tds[1].get_text(strip=True)

            a_tag = tds[2].find("a")
            if a_tag:
                title = a_tag.get_text(strip=True)
                data_action = a_tag.get("data-action", "")
                if data_action:
                    detail_url = f"{BASE_URL}{data_action}"
                else:
                    detail_url = f"{LIST_URL}?seCode=01&mid=0401040000"
            else:
                title = tds[2].get_text(strip=True)
                detail_url = f"{LIST_URL}?seCode=01&mid=0401040000"

            dept = tds[4].get_text(strip=True)
            date_str = tds[5].get_text(strip=True) if len(tds) > 5 else ""

            items.append({
                "number": number,
                "title": f"[{gosi_no}] {title}" if gosi_no else title,
                "date": date_str,
                "url": detail_url,
                "organization": f"{ORGANIZATION_NAME} ({dept})" if dept else ORGANIZATION_NAME,
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
        print(f"[{ORGANIZATION_NAME} 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GumiGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
