# -*- coding: utf-8 -*-
"""
서산시청 입찰공고 크롤러
https://www.seosan.go.kr/www/contents.do?key=1259
eminwon iframe 기반 (contents.do -> OfrAction.do), POST, not_ancmt_se_code=02, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


EMINWON_BASE = "https://eminwon.seosan.go.kr"
ACTION_URL = f"{EMINWON_BASE}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
DETAIL_URL = f"{EMINWON_BASE}/emwp/jsp/ofr/OfrNotAncmtVSub.jsp"
SE_CODE = "02"
PAGE_SIZE = 10
ORGANIZATION_NAME = "서산시청"


class SeosanBidCrawler:
    """서산시청 입찰공고 크롤러"""

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
            "not_ancmt_se_code": SE_CODE,
            "title": "입찰공고",
            "countYn": "Y",
            "list_gubun": "A",
            "not_ancmt_sj": keyword if keyword else "",
            "not_ancmt_cn": "",
            "dept_nm": "",
            "temp": "",
        }

        resp = self.session.post(ACTION_URL, data=data, timeout=30)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []

        for tr in soup.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            ths = tr.find_all("th", recursive=False)
            if len(ths) == 1 and len(tds) >= 4:
                number = ths[0].get_text(strip=True)
                if not number.isdigit():
                    continue
                if total_count == 0 and page == 1:
                    total_count = int(number)
                gosi_no = tds[0].get_text(strip=True)
                title_text = tds[1].get_text(strip=True)
                dept = tds[2].get_text(strip=True)
                date = tds[3].get_text(strip=True).replace(".", "-")
                link = tds[1].find("a")
                detail_url = ""
                if link:
                    onclick = link.get("onclick", "") or link.get("href", "")
                    m = re.search(r"searchDetail\(['\"]?(\d+)['\"]?\)", onclick)
                    if m:
                        detail_url = (
                            f"{DETAIL_URL}?not_ancmt_se_code={SE_CODE}"
                            f"&not_ancmt_mgt_no={m.group(1)}"
                        )
                items.append({
                    "number": number,
                    "title": f"[{gosi_no}] {title_text}" if gosi_no else title_text,
                    "date": date,
                    "url": detail_url,
                    "organization": f"{ORGANIZATION_NAME} ({dept})" if dept else ORGANIZATION_NAME,
                })
                continue
            if len(tds) < 6:
                continue
            number = tds[0].get_text(strip=True)
            if not number.isdigit():
                continue
            if total_count == 0 and page == 1:
                total_count = int(number)
            gosi_no = tds[1].get_text(strip=True)
            title_text = tds[2].get_text(strip=True)
            dept = tds[3].get_text(strip=True)
            date = tds[4].get_text(strip=True).replace(".", "-")
            link = tds[2].find("a")
            detail_url = ""
            if link:
                onclick = link.get("onclick", "") or link.get("href", "")
                m = re.search(r"searchDetail\(['\"]?(\d+)['\"]?\)", onclick)
                if m:
                    detail_url = (
                        f"{DETAIL_URL}?not_ancmt_se_code={SE_CODE}"
                        f"&not_ancmt_mgt_no={m.group(1)}"
                    )
            items.append({
                "number": number,
                "title": f"[{gosi_no}] {title_text}" if gosi_no else title_text,
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
        print(f"[{ORGANIZATION_NAME} 입찰] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = SeosanBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
