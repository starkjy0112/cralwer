# -*- coding: utf-8 -*-
"""
논산시청 공고 크롤러
https://nonsan.go.kr/kor/html/sub03/030105.html
iframe 내 eminwon 시스템 (OfrAction.do), POST 기반, 10건/페이지
not_ancmt_se_code=04 (공고)
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


ACTION_URL = "https://eminwon.nonsan21.net/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
DETAIL_URL = "https://eminwon.nonsan21.net/emwp/jsp/ofr/OfrNotAncmtVSub.jsp"
SE_CODE = "04"
PAGE_SIZE = 10
ORGANIZATION_NAME = "논산시청"


class NonsanCrawler:
    """논산시청 입찰공고 크롤러"""

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
            "homepage_pbs_yn": "Y",
            "subCheck": "Y",
            "ofr_pageSize": str(PAGE_SIZE),
            "not_ancmt_se_code": SE_CODE,
            "title": "",
            "countYn": "Y",
            "not_ancmt_sj": "",
            "not_ancmt_cn": "",
            "dept_nm": "",
            "Key": "B_Subject",
            "temp": "",
            "not_ancmt_mgt_no": "",
            "initValue": "",
            "cha_dep_code_nm": "",
            "yyyy": "",
            "list_gubun": "",
        }
        if keyword:
            data["not_ancmt_sj"] = keyword
            data["temp"] = keyword

        resp = self.session.post(ACTION_URL, data=data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        total_count = 0
        items = []
        table = soup.find("table")
        if table:
            rows = table.find_all("tr")
            for tr in rows:
                # 각 행: <th>번호</th> <td>고시번호</td> <td>제목</td> <td>부서</td> <td>날짜</td> <td>조회</td>
                ths = tr.find_all("th")
                tds = tr.find_all("td")
                if len(ths) == 1 and len(tds) >= 4:
                    number = ths[0].get_text(strip=True)
                    if not number.isdigit():
                        continue
                    if not total_count:
                        total_count = int(number)
                    gosi_no = tds[0].get_text(strip=True)
                    title_td = tds[1]
                    title_tag = title_td.find("a")
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                        href = title_tag.get("href", "")
                        m = re.search(r"searchDetail\(['\"]?(\d+)['\"]?\)", href)
                        if m:
                            detail_url = f"{DETAIL_URL}?not_ancmt_mgt_no={m.group(1)}"
                        else:
                            detail_url = ""
                    else:
                        title = tds[1].get_text(strip=True)
                        detail_url = ""
                    dept = tds[2].get_text(strip=True)
                    date = tds[3].get_text(strip=True).replace(".", "-")

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
    crawler = NonsanCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
