# -*- coding: utf-8 -*-
"""
보령시청 고시공고 크롤러
https://www.brcn.go.kr/prog/eminwon/kor/BB/sub04_03_01/list.do
GET 기반, 서버검색 미지원(클라이언트 필터), 4컬럼(순번/제목/부서명/등록일), 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.brcn.go.kr"
LIST_URL = f"{BASE_URL}/prog/eminwon/kor/BB/sub04_03_01/list.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "보령시청"


class BoryeongCrawler:
    """보령시청 고시공고 크롤러"""

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
            "pageIndex": str(page),
        }
        if keyword:
            params["searchCondition"] = "subject"
            params["searchKeyword"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []
        table = soup.find("table")
        if not table:
            return items, total_count

        rows = table.find_all("tr")
        for tr in rows:
            tds = tr.find_all("td")
            # 4컬럼: 순번, 제목, 부서명, 등록일
            if len(tds) < 4:
                continue
            number = tds[0].get_text(strip=True)
            if not number.isdigit():
                continue
            if not total_count:
                total_count = int(number)

            title_td = tds[1]
            a_tag = title_td.find("a")
            if a_tag:
                title = a_tag.get_text(strip=True)
                href = a_tag.get("href", "")
                if href.startswith("/"):
                    detail_url = f"{BASE_URL}{href}"
                elif href.startswith("?"):
                    detail_url = f"{LIST_URL}{href}"
                else:
                    detail_url = href if href.startswith("http") else LIST_URL
            else:
                title = title_td.get_text(strip=True)
                detail_url = LIST_URL

            dept = tds[2].get_text(strip=True)
            date_str = tds[3].get_text(strip=True).replace(".", "-")

            items.append({
                "number": number,
                "title": title,
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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = BoryeongCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
