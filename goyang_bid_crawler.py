# -*- coding: utf-8 -*-
"""
고양특례시청 입찰공고 크롤러
https://www.goyang.go.kr/www/link/BD_bidding.do
GET 기반 (eminwon iframe), 10건/페이지
실제 데이터는 https://eminwon.goyang.go.kr 새올행정포털에서 제공
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

EMINWON_URL = "https://eminwon.goyang.go.kr/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
DETAIL_URL = EMINWON_URL
PAGE_SIZE = 100


class GoyangBidCrawler:
    """고양특례시청 입찰공고 크롤러"""

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
        self.session.verify = False

    def _fetch_page(self, keyword, page):
        params = {
            "jndinm": "OfrNotAncmtEJB",
            "context": "NTIS",
            "method": "selectListOfrNotAncmt",
            "methodnm": "selectListOfrNotAncmtHomepage",
            "homepage_pbs_yn": "Y",
            "subCheck": "Y",
            "not_ancmt_se_code": "02",
            "initValue": "Y",
            "countYn": "Y",
            "epcCheck": "Y",
            "ofr_pageSize": str(PAGE_SIZE),
        }
        if page > 1:
            params["pageIndex"] = str(page)
        if keyword:
            params["not_ancmt_sj"] = keyword
        resp = self.session.get(EMINWON_URL, params=params, timeout=30)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        total_el = soup.select_one(".bbs-total strong") or soup.select_one(".list-header strong")
        if total_el:
            total_count = int(total_el.get_text(strip=True).replace(",", ""))

        items = []
        tbody = soup.select_one("table.table-list tbody")
        if not tbody:
            return items, total_count
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            number = tds[0].get_text(strip=True)
            gosi_no_el = tds[1].find("a")
            gosi_no = tds[1].get_text(strip=True)
            a_tag = tds[2].find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            # Extract not_ancmt_mgt_no from javascript:searchDetail('...')
            onclick = a_tag.get("href", "")
            mgt_no_match = re.search(r"searchDetail\('(\d+)'\)", onclick)
            detail_url = ""
            if mgt_no_match:
                mgt_no = mgt_no_match.group(1)
                detail_url = (
                    f"{EMINWON_URL}?jndinm=OfrNotAncmtEJB&context=NTIS"
                    f"&method=selectOfrNotAncmt&methodnm=selectOfrNotAncmtRegst"
                    f"&not_ancmt_mgt_no={mgt_no}"
                )
            dept = tds[3].get_text(strip=True)
            date = tds[4].get_text(strip=True)
            items.append({
                "number": number,
                "title": f"[{gosi_no}] {title}" if gosi_no else title,
                "date": date,
                "url": detail_url,
                "organization": f"고양특례시청 ({dept})",
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
        print(f"[고양특례시청 입찰공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GoyangBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
