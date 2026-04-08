# -*- coding: utf-8 -*-
"""
진안군청 고시공고 크롤러
https://www.jinan.go.kr/index.jinan?menuCd=DOM_000000107001014000
iframe -> eminwon (OfrNotAncmtLSub.jsp -> OfrAction.do), POST 기반, 10건/페이지
OfrNotAncmtL 변형: td onclick="searchDetail('id')" 패턴
"""
import math
import re
from datetime import datetime, timedelta
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

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        # 날짜 기본값 (최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        all_items = []
        stop = False

        # 첫 페이지 날짜 필터
        for item in first_items:
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if not d:
                continue
            if d < start_date:
                stop = True
                continue
            if d <= end_date:
                all_items.append(item)

        # 나머지 페이지 순차 수집 + early stop
        if not stop and actual_pages > 1:
            page = 2
            while page <= actual_pages and not stop:
                # 배치 단위로 병렬 수집
                batch_end = min(page + self.WORKERS, actual_pages + 1)
                with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                    futures = {
                        executor.submit(self._fetch_page, keyword, p): p
                        for p in range(page, batch_end)
                    }
                    batch_results = {}
                    for future in as_completed(futures):
                        p = futures[future]
                        try:
                            items, _ = future.result()
                            if items:
                                batch_results[p] = items
                        except Exception:
                            pass

                # 페이지 순서대로 날짜 체크
                for p in sorted(batch_results.keys()):
                    for item in batch_results[p]:
                        d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
                        if not d:
                            continue
                        if d < start_date:
                            stop = True
                            break
                        if d <= end_date:
                            all_items.append(item)
                    if stop:
                        break

                page = batch_end

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
