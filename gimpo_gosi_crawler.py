# -*- coding: utf-8 -*-
"""
김포시청 고시공고 크롤러
https://www.gimpo.go.kr/portal/ntfcPblancList.do?key=1004&cate_cd=1&searchCnd=40900000000
GET 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.gimpo.go.kr"
LIST_URL = f"{BASE_URL}/portal/ntfcPblancList.do"
PAGE_SIZE = 10


class GimpoGosiCrawler:
    """김포시청 고시공고 크롤러"""

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
            "key": "1004",
            "cate_cd": "1",
            "pageIndex": str(page),
        }
        if keyword:
            params["searchCnd"] = "not_ancmt_sj"
            params["searchKrwd"] = keyword
        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        em = soup.select_one(".em_black")
        if em:
            total_count = int(em.get_text(strip=True).replace(",", ""))

        items = []
        tbody = soup.select_one("table.p-table tbody")
        if not tbody:
            return items, total_count
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            number = tds[0].get_text(strip=True).replace(",", "")
            gosi_no = tds[1].get_text(strip=True)
            a_tag = tds[2].find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if href.startswith("./"):
                href = f"{BASE_URL}/portal/{href[2:]}"
            elif href.startswith("/"):
                href = f"{BASE_URL}{href}"
            dept = tds[3].get_text(strip=True)
            date = tds[4].get_text(strip=True)
            items.append({
                "number": number,
                "title": f"[{gosi_no}] {title}" if gosi_no else title,
                "date": date,
                "url": href,
                "organization": f"김포시청 ({dept})",
            })
        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
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
        # 날짜 필터 (기본: 최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        filtered = []
        for item in all_items:
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if not d:
                continue
            if start_date <= d <= end_date:
                filtered.append(item)
        all_items = filtered

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[김포시청 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GimpoGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
