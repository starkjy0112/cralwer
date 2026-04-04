# -*- coding: utf-8 -*-
"""
예산군청 고시공고 크롤러
https://www.yesan.go.kr/prog/saeolGosi/GOSI/kor/sub04_03_01/list.do
GET 기반, table.bbsTable, 20건/페이지, pageIndex 파라미터
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.yesan.go.kr"
LIST_URL = f"{BASE_URL}/prog/saeolGosi/GOSI/kor/sub04_03_01/list.do"
PAGE_SIZE = 20
ORGANIZATION_NAME = "예산군청"


class YesanGosiCrawler:
    """예산군청 고시공고 크롤러"""

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

    def _fetch_page(self, keyword, page):
        params = {
            "pageIndex": str(page),
        }
        if keyword:
            params["searchCondition"] = "sj"
            params["searchKeyword"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        m = re.search(r'총\s*([\d,]+)\s*건', soup.get_text())
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table.bbsTable") or soup.select_one("table")
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

            # Title: button.button_view with data-list-no, or a tag, or plain text
            btn = tds[2].find("button", class_="button_view")
            a_tag = tds[2].find("a")
            if btn:
                title = btn.get_text(strip=True)
                list_no = btn.get("data-list-no", "")
                detail_url = f"{LIST_URL}?mode=view&cntNo={list_no}" if list_no else LIST_URL
            elif a_tag:
                title = a_tag.get_text(strip=True)
                href = a_tag.get("href", "")
                if href.startswith("/"):
                    detail_url = f"{BASE_URL}{href}"
                elif href.startswith("?"):
                    detail_url = f"{LIST_URL}{href}"
                else:
                    detail_url = href if href.startswith("http") else LIST_URL
            else:
                title = tds[2].get_text(strip=True)
                detail_url = LIST_URL

            dept = tds[3].get_text(strip=True)
            date_str = tds[4].get_text(strip=True).replace(".", "-")

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
    crawler = YesanGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
