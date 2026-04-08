# -*- coding: utf-8 -*-
"""
태안군청 일반공고 크롤러
https://www.taean.go.kr/kor/sub02_03_03.do
iframe -> eminwon POST 기반, OfrAction.do, not_ancmt_se_code=01,04,06
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://eminwon.taean.go.kr"
LIST_URL = f"{BASE_URL}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
JSP_URL = f"{BASE_URL}/emwp/jsp/ofr/OfrNotAncmtL.jsp"
DETAIL_BASE = f"{BASE_URL}/emwp/jsp/ofr/OfrNotAncmtLSub.jsp"
PAGE_SIZE = 10
ORGANIZATION_NAME = "태안군청"


class TaeanGosiCrawler:
    """태안군청 일반공고 크롤러"""

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
        self._initialized = False

    def _init_session(self):
        if not self._initialized:
            try:
                self.session.get(
                    f"{JSP_URL}?not_ancmt_se_code=01,04,06&list_gubun=A",
                    timeout=15
                )
            except Exception:
                pass
            self._initialized = True

    def _fetch_page(self, keyword, page):
        self._init_session()
        data = {
            "pageIndex": str(page),
            "jndinm": "OfrNotAncmtEJB",
            "context": "NTIS",
            "method": "selectListOfrNotAncmt",
            "methodnm": "selectListOfrNotAncmtHomepage",
            "not_ancmt_mgt_no": "",
            "homepage_pbs_yn": "Y",
            "subCheck": "Y",
            "ofr_pageSize": str(PAGE_SIZE),
            "not_ancmt_se_code": "01,04,06",
            "title": "",
            "countYn": "Y",
            "list_gubun": "A",
            "not_ancmt_sj": keyword if keyword else "",
            "not_ancmt_cn": "",
            "dept_nm": "",
            "temp": "",
        }

        resp = self.session.post(LIST_URL, data=data, timeout=30)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []

        for tr in soup.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 5:
                continue

            number = tds[0].get_text(strip=True)
            if not number.isdigit():
                continue

            if total_count == 0 and page == 1:
                total_count = int(number)

            gosi_no = tds[1].get_text(strip=True)
            title_text = tds[2].get_text(strip=True)
            dept = tds[3].get_text(strip=True) if len(tds) > 3 else ""
            date = tds[4].get_text(strip=True) if len(tds) > 4 else ""

            link = tds[2].find("a")
            detail_url = ""
            if link:
                onclick = link.get("onclick", "")
                m = re.search(r"searchDetail\('(\d+)'\)", onclick)
                if m:
                    mgt_no = m.group(1)
                    detail_url = f"{DETAIL_BASE}?not_ancmt_mgt_no={mgt_no}"

            items.append({
                "number": number,
                "title": f"[{gosi_no}] {title_text}" if gosi_no else title_text,
                "date": date,
                "url": detail_url,
                "organization": f"{ORGANIZATION_NAME} ({dept})" if dept else ORGANIZATION_NAME,
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
        print(f"[{ORGANIZATION_NAME} 일반공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = TaeanGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
