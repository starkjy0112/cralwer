# -*- coding: utf-8 -*-
"""
남양주시청 고시공고 크롤러
https://www.nyj.go.kr/www/selectEminwonWebList.do?key=2492&sa1=01&sa1=02&sa1=04&sa1=05
POST 기반, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.nyj.go.kr"
LIST_URL = f"{BASE_URL}/www/selectEminwonWebList.do"
PAGE_SIZE = 100


class NamyangjuCrawler:
    """남양주시청 고시공고 크롤러"""

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
        data = {
            "key": "2492",
            "sa1": ["01", "02", "04", "05"],
            "pageIndex": str(page),
            "rcpp": str(PAGE_SIZE),
        }
        if keyword:
            data["sc1"] = "SJ"
            data["sc2"] = keyword
        resp = self.session.post(LIST_URL, data=data, timeout=15)
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
            if len(tds) < 4:
                continue
            number = tds[0].get_text(strip=True).replace(",", "")
            # Column 1 has gosi_no + title (with <br/> and <a>)
            td_title = tds[1]
            a_tag = td_title.find("a")
            if not a_tag:
                continue
            title_text = a_tag.get_text(strip=True)
            # Get gosi_no from text before <a>
            full_text = td_title.get_text(separator="|", strip=True)
            parts = full_text.split("|")
            gosi_no = parts[0].strip() if len(parts) > 1 else ""
            href = a_tag.get("href", "")
            if href.startswith("./"):
                href = f"{BASE_URL}/www/{href[2:]}"
            elif href.startswith("/"):
                href = f"{BASE_URL}{href}"
            dept = tds[2].get_text(strip=True)
            date = tds[3].get_text(strip=True)
            items.append({
                "number": number,
                "title": f"[{gosi_no}] {title_text}" if gosi_no else title_text,
                "date": date,
                "url": href,
                "organization": f"남양주시청 ({dept})",
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
        print(f"[남양주시청 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = NamyangjuCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
