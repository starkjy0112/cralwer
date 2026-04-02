# -*- coding: utf-8 -*-
"""
안산시청 고시/공고 크롤러
https://www.ansan.go.kr/www/common/bbs/selectPageListBbs.do?bbs_code=WWW13
GET 기반, 15건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.ansan.go.kr"
LIST_URL = f"{BASE_URL}/www/common/bbs/selectPageListBbs.do"
DETAIL_URL = f"{BASE_URL}/www/common/bbs/selectBbsDetail.do"
PAGE_SIZE = 15
ORGANIZATION_NAME = "안산시청"
BBS_CODE = "WWW13"


class AnsanGosiCrawler:
    """안산시청 고시/공고 크롤러"""

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
            "bbs_code": BBS_CODE,
            "currentPage": str(page),
        }
        if keyword:
            params["sch_text"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # Parse total count from pagination
        total_count = 0
        paging = soup.find("div", class_="paging") or soup.find("div", class_="pagination")
        if paging:
            max_page = 1
            for a in paging.find_all("a"):
                onclick = a.get("onclick", "")
                nums = re.findall(r'fnGoPage\(\s*(\d+)\s*\)', onclick)
                for n in nums:
                    if int(n) > max_page:
                        max_page = int(n)
            total_count = max_page * PAGE_SIZE

        # Also try to get count from first td text like "14310"
        items = []
        table = None
        for t in soup.find_all("table"):
            rows = t.find_all("tr")
            if len(rows) > 5:
                table = t
                break

        if table:
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 5:
                    continue
                # 번호, 고시공고번호, 제목, 담당부서, 작성일
                number = tds[0].get_text(strip=True)
                if not total_count and number.isdigit():
                    total_count = int(number)

                title_td = tds[2]
                title_tag = title_td.find("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                # onclick="fnGoDetail( 1667009 ); return false;"
                onclick = title_tag.get("onclick", "")
                m_seq = re.search(r"fnGoDetail\(\s*(\d+)\s*\)", onclick)
                if m_seq:
                    detail_url = f"{DETAIL_URL}?bbs_code={BBS_CODE}&bbs_seq={m_seq.group(1)}"
                else:
                    detail_url = ""
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
    crawler = AnsanGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
