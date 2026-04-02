# -*- coding: utf-8 -*-
"""
정선군청 공고/고시 크롤러
https://www.jeongseon.go.kr/portal/openadmin/adminnews/notification
e-minwon iframe 기반, POST to OfrAction.do, not_ancmt_se_code=01,04,05,06
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "http://eminwon.jeongseon.go.kr"
JSP_URL = f"{BASE_URL}/emwp/jsp/ofr/OfrNotAncmtLSub.jsp"
ACTION_URL = f"{BASE_URL}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "정선군청"
SE_CODE = "01,04,05,06"


class JeongseonGosiCrawler:
    """정선군청 공고/고시 크롤러"""

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
        try:
            self.session.get(
                f"{JSP_URL}?not_ancmt_se_code={SE_CODE}&homepage_pbs_yn=Y&subCheck=Y",
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
            "not_ancmt_se_code": SE_CODE,
            "homepage_pbs_yn": "Y",
            "subCheck": "Y",
            "ofr_pageSize": str(PAGE_SIZE),
            "countYn": "Y",
            "not_ancmt_sj": "",
            "not_ancmt_cn": "",
            "dept_nm": "",
            "not_ancmt_reg_no": "",
        }
        if keyword:
            data["not_ancmt_sj"] = keyword

        resp = self.session.post(ACTION_URL, data=data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        text = soup.get_text()
        m = re.search(r'전체게시물\s*:\s*(\d[\d,]*)\s*개', text)
        if not m:
            m = re.search(r'(\d[\d,]*)\s*건', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            # 번호, 고시공고번호, 제목, 부서, 등록일
            if len(cells) != 5:
                continue
            # 첫 번째 셀이 숫자인지 확인
            first_text = cells[0].get_text(strip=True)
            if not first_text.isdigit():
                continue

            number = first_text
            notice_no = cells[1].get_text(strip=True)
            title = cells[2].get_text(strip=True)
            dept = cells[3].get_text(strip=True)
            date = cells[4].get_text(strip=True)

            items.append({
                "number": notice_no if notice_no else number,
                "title": title,
                "date": date,
                "url": "https://www.jeongseon.go.kr/portal/openadmin/adminnews/notification",
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
        print(f"[{ORGANIZATION_NAME} 공고/고시] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = JeongseonGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
