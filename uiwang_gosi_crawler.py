# -*- coding: utf-8 -*-
"""
의왕시청 고시공고 크롤러
https://www.uiwang.go.kr/UWKORINFO0701
e-minwon iframe 기반, POST to OfrAction.do, not_ancmt_se_code=01,04,06
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://eminwon.uiwang.go.kr"
JSP_URL = f"{BASE_URL}/emwp/jsp/ofr/OfrNotAncmtL.jsp"
ACTION_URL = f"{BASE_URL}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
PAGE_SIZE = 100


class UiwangGosiCrawler:
    """의왕시청 고시공고 크롤러"""

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
        # 세션 초기화 (쿠키 획득)
        try:
            self.session.get(
                f"{JSP_URL}?not_ancmt_se_code=01,04,06&homepage_pbs_yn=Y&subCheck=Y&list_gubun=A",
                timeout=15)
        except Exception:
            pass

    def _fetch_page(self, keyword, page):
        data = {
            "pageIndex": str(page),
            "jndinm": "OfrNotAncmtEJB",
            "context": "NTIS",
            "method": "selectListOfrNotAncmt",
            "methodnm": "selectListOfrNotAncmtHomepage",
            "not_ancmt_se_code": "01,04,06",
            "homepage_pbs_yn": "Y",
            "subCheck": "Y",
            "ofr_pageSize": str(PAGE_SIZE),
            "countYn": "Y",
            "list_gubun": "A",
            "nodate_recent_mm": "",
            "nodate_last_mm": "",
            "recent_mm": "",
            "last_mm": "",
            "yyyy": "",
            "yyyymmdd": "",
        }
        if keyword:
            data["not_ancmt_sj"] = keyword

        resp = self.session.post(ACTION_URL, data=data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: "전체게시물:N개"
        total_count = 0
        text = soup.get_text()
        m = re.search(r'전체게시물\s*:\s*(\d[\d,]*)\s*개', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        # 데이터는 onclick="searchDetail('ID')" 패턴의 td에 있음
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) == 6:
                onclick = cells[0].get("onclick", "")
                if "searchDetail" not in onclick:
                    continue
                number = cells[0].get_text(strip=True)
                notice_no = cells[1].get_text(strip=True)
                title = cells[2].get_text(strip=True)
                dept = cells[3].get_text(strip=True)
                date = cells[4].get_text(strip=True)

                items.append({
                    "number": notice_no if notice_no else number,
                    "title": title,
                    "date": date,
                    "url": "https://www.uiwang.go.kr/UWKORINFO0701",
                    "organization": "의왕시청",
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
        print(f"[의왕시청 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = UiwangGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
