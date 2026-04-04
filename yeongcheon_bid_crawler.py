# -*- coding: utf-8 -*-
"""
영천시청 입찰공고 크롤러
https://www.yc.go.kr/portal/bbs/list.do?ptIdx=568&mId=0301030000
POST 기반, 10건/페이지, bod_list, list_tit/list_date
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.yc.go.kr"
LIST_URL = f"{BASE_URL}/portal/bbs/list.do"
PT_IDX = "568"
MID = "0301030000"
PAGE_SIZE = 10
ORGANIZATION_NAME = "영천시청"


class YeongcheonBidCrawler:
    """영천시청 입찰공고 크롤러"""

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
            "ptIdx": PT_IDX,
            "mId": MID,
            "page": str(page),
        }
        if keyword:
            params["searchType"] = "tit"
            params["searchTxt"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        page_num = soup.find("p", class_="page_num")
        if page_num:
            m = re.search(r"전체\s*페이지\s*([\d,]+)", page_num.get_text())
            if m:
                total_count = int(m.group(1).replace(",", "")) * PAGE_SIZE

        items = []
        table = soup.select_one("table.bod_list")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 3:
                continue

            number = row.select_one("td.list_num")
            number = number.get_text(strip=True) if number else tds[0].get_text(strip=True)

            if total_count == 0 and page == 1 and number.replace(",", "").isdigit():
                total_count = int(number.replace(",", ""))

            title_td = row.select_one("td.list_tit")
            if not title_td:
                for td in tds:
                    if td.find("a"):
                        title_td = td
                        break
            if not title_td:
                continue
            link = title_td.find("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            for img in link.select("img"):
                alt = img.get("alt", "")
                title = title.replace(alt, "").strip()

            data_action = link.get("data-action", "")
            href = link.get("href", "")
            if data_action:
                detail_url = f"{BASE_URL}{data_action}"
            elif href and href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            elif href and href.startswith("http"):
                detail_url = href
            else:
                detail_url = ""

            date_td = row.select_one("td.list_date")
            date = date_td.get_text(strip=True) if date_td else ""

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
        print(f"[{ORGANIZATION_NAME} 입찰공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = YeongcheonBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
