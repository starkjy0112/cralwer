# -*- coding: utf-8 -*-
"""
괴산군청 고시/공고 크롤러
https://www.goesan.go.kr/www/contents.do?key=1438
실제 데이터는 eminwon.goesan.go.kr OfrAction으로 제공
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

EMINWON_URL = "https://eminwon.goesan.go.kr/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "괴산군청"


class GoesanGosiCrawler:
    """괴산군청 고시/공고 크롤러"""

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
            "jndinm": "OfrNotAncmtEJB",
            "context": "NTIS",
            "method": "selectListOfrNotAncmt",
            "methodnm": "selectListOfrNotAncmtHomepage",
            "homepage_pbs_yn": "Y",
            "subCheck": "Y",
            "not_ancmt_se_code": "01,02,03,04",
            "initValue": "Y",
            "countYn": "Y",
            "ofr_pageSize": str(PAGE_SIZE),
            "list_gubun": "A",
            "epcCheck": "Y",
        }
        if page > 1:
            params["pageIndex"] = str(page)
        if keyword:
            params["not_ancmt_sj"] = keyword
        resp = self.session.get(EMINWON_URL, params=params, timeout=30)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []
        tbody = soup.select_one("table.table_list tbody") or soup.select_one("table.table-list tbody")
        if not tbody:
            return items, total_count
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            number = tds[0].get_text(strip=True)
            if not total_count and page == 1 and number.isdigit():
                total_count = int(number)

            gosi_no = tds[1].get_text(strip=True)
            title_text = tds[2].get_text(strip=True)
            title = f"[{gosi_no}] {title_text}" if gosi_no else title_text

            # Links via onclick on td or a tags
            onclick = tds[0].get("onclick", "") or tds[2].get("onclick", "")
            a_tag = tds[2].find("a")
            if a_tag:
                onclick = a_tag.get("href", "") or a_tag.get("onclick", "") or onclick
            mgt_match = re.search(r"searchDetail\('(\d+)'\)", onclick)
            detail_url = ""
            if mgt_match:
                detail_url = (
                    f"{EMINWON_URL}?jndinm=OfrNotAncmtEJB&context=NTIS"
                    f"&method=selectOfrNotAncmt&methodnm=selectOfrNotAncmtRegst"
                    f"&not_ancmt_mgt_no={mgt_match.group(1)}"
                )

            dept = tds[3].get_text(strip=True)
            date = tds[4].get_text(strip=True).replace(".", "-")

            items.append({
                "number": number,
                "title": title,
                "date": date,
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
        print(f"[{ORGANIZATION_NAME} 고시/공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = GoesanGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n=== '용역' 검색 ===")
    results2 = crawler.search("용역", max_pages=1)
    for r in results2[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n공고: {len(results)}건, 용역: {len(results2)}건")
