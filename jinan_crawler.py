# -*- coding: utf-8 -*-
"""
진안군청 고시공고 크롤러
https://www.jinan.go.kr/index.jinan?menuCd=DOM_000000107001014000
iframe -> eminwon (OfrNotAncmtLSub.jsp -> OfrAction.do), POST 기반, 10건/페이지
OfrNotAncmtL 변형: td onclick="searchDetail('id')" 패턴
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed


EMINWON_BASE = "https://eminwon.jinan.go.kr"
ACTION_URL = f"{EMINWON_BASE}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
DETAIL_URL = f"{EMINWON_BASE}/emwp/jsp/ofr/OfrNotAncmtVSub.jsp"
SE_CODES = "01,02,03,04,05"
PAGE_SIZE = 10
ORGANIZATION_NAME = "진안군청"


class JinanCrawler:
    """진안군청 고시공고 크롤러"""

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
            "not_ancmt_se_code": SE_CODES,
            "countYn": "Y",
            "not_ancmt_sj": keyword if keyword else "",
            "temp": keyword if keyword else "",
        }

        resp = self.session.post(ACTION_URL, data=data, timeout=30)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        total_count = 0
        m_total = re.search(r'전체게시물\s*:\s*(\d+)\s*개', resp.text)
        if m_total:
            total_count = int(m_total.group(1))

        items = []
        # Group tds by searchDetail ID
        groups = defaultdict(list)
        order = []
        for td in soup.find_all("td", onclick=re.compile(r"searchDetail")):
            m = re.search(r"searchDetail\('(\d+)'\)", td.get("onclick", ""))
            if m:
                gid = m.group(1)
                if gid not in groups:
                    order.append(gid)
                groups[gid].append(td.get_text(strip=True))

        for gid in order:
            texts = groups[gid]
            if len(texts) < 5:
                continue
            # [번호, 공고번호, 제목, 부서, 등록일, (조회)]
            number = texts[0]
            gosi_no = texts[1]
            title = texts[2]
            date = texts[4]
            detail_url = f"{DETAIL_URL}?not_ancmt_mgt_no={gid}"

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
        print(f"[{ORGANIZATION_NAME} 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = JinanCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
