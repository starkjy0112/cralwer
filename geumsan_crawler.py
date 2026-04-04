# -*- coding: utf-8 -*-
"""
금산군청 고시/공고 크롤러
https://www.geumsan.go.kr/kr/html/sub03/030302.html
PCMS 게시판, GET 기반, skey/sval 검색, GotoPage 페이지네이션, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.geumsan.go.kr"
LIST_URL = f"{BASE_URL}/kr/html/sub03/030302.html"
DETAIL_BASE = f"{BASE_URL}/site/kr/html/sub03/030302.html"
PAGE_SIZE = 10
ORGANIZATION_NAME = "금산군청"


class GeumsanCrawler:
    """금산군청 고시/공고 크롤러"""

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
            "site_dvs_cd": "kr",
            "menu_dvs_cd": "030302",
            "GotoPage": str(page),
        }
        if keyword:
            params["skey"] = "title"
            params["sval"] = keyword
        else:
            params["skey"] = ""
            params["sval"] = ""

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        total_count = 0
        last_link = soup.find("a", string=re.compile(r"마지막.*페이지"))
        if last_link:
            href = last_link.get("href", "")
            m = re.search(r"GotoPage=(\d+)", href)
            if m:
                total_count = int(m.group(1)) * PAGE_SIZE

        items = []
        table = soup.find("table")
        if table:
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 5:
                    continue
                number = tds[0].get_text(strip=True)
                if not total_count and number.isdigit():
                    total_count = int(number)
                gosi_no = tds[1].get_text(strip=True)
                title_td = tds[2]
                title_tag = title_td.find("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                if href and not href.startswith("http"):
                    detail_url = BASE_URL + href
                else:
                    detail_url = href
                dept = tds[3].get_text(strip=True)
                date_text = tds[4].get_text(strip=True)
                # 게재기간 형식: "2026-04-03~2026-04-08" -> 등록일 추출
                date = date_text.split("~")[0].strip() if "~" in date_text else date_text

                items.append({
                    "number": number,
                    "title": f"[{gosi_no}] {title}" if gosi_no else title,
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
    crawler = GeumsanCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
