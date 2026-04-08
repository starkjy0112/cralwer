# -*- coding: utf-8 -*-
"""
서초구청 고시공고 크롤러
https://www.seocho.go.kr/site/seocho/05/10506020000002015070811.jsp
실제 데이터는 iframe 내 eminwon 시스템:
https://eminwon.seocho.go.kr/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do
POST 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


EMINWON_BASE = "https://eminwon.seocho.go.kr"
LIST_URL = f"{EMINWON_BASE}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
INIT_URL = f"{EMINWON_BASE}/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,02,04"
PAGE_SIZE = 100
ORGANIZATION_NAME = "서초구청"


class SeochoCrawler:
    """서초구청 고시공고 크롤러"""

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
        # Initialize session cookies
        try:
            self.session.get(INIT_URL, timeout=15)
        except Exception:
            pass

    def _fetch_page(self, keyword, page):
        data = {
            "pageIndex": str(page),
            "jndinm": "OfrNotAncmtEJB",
            "context": "NTIS",
            "method": "selectListOfrNotAncmt",
            "methodnm": "selectListOfrNotAncmtHomepage",
            "homepage_pbs_yn": "Y",
            "subCheck": "Y",
            "not_ancmt_se_code": "01,02,04",
            "title": "고시공고",
            "countYn": "Y",
            "epcCheck": "Y",
            "ofr_pageSize": str(PAGE_SIZE),
            "initValue": "Y",
        }
        if keyword:
            data["not_ancmt_sj"] = keyword

        resp = self.session.post(LIST_URL, data=data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        text = soup.get_text()
        m = re.search(r'전체게시물\s*:\s*([\d,]+)\s*개', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))
        if not total_count:
            m2 = re.search(r'페이지\s*:\s*\d+\s*/\s*(\d+)', text)
            if m2:
                total_count = int(m2.group(1)) * PAGE_SIZE

        items = []
        table = soup.select_one("table.list, table")
        if not table:
            return items, total_count

        rows = table.select("tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            # 번호, 고시공고번호, 제목, 담당부서, 등록일, 게재기간
            number = cells[0].get_text(strip=True)
            gosi_no = cells[1].get_text(strip=True)
            title_cell = cells[2]
            a_tag = title_cell.select_one("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)

            onclick = a_tag.get("onclick", "") or a_tag.get("href", "")
            mgt_no_match = re.search(r"searchDetail\('(\d+)'\)", onclick)
            if mgt_no_match:
                mgt_no = mgt_no_match.group(1)
                detail_url = (
                    f"{LIST_URL}?jndinm=OfrNotAncmtEJB&context=NTIS"
                    f"&method=selectOfrNotAncmt&methodnm=selectOfrNotAncmtRegst"
                    f"&not_ancmt_mgt_no={mgt_no}"
                )
            else:
                detail_url = "https://www.seocho.go.kr/site/seocho/05/10506020000002015070811.jsp"

            dept = cells[3].get_text(strip=True) if len(cells) > 3 else ORGANIZATION_NAME
            date_str = cells[4].get_text(strip=True) if len(cells) > 4 else ""

            m = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', date_str)
            if m:
                date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

            items.append({
                "number": number,
                "title": f"[{gosi_no}] {title}" if gosi_no else title,
                "date": date_str,
                "url": detail_url,
                "organization": dept if dept else ORGANIZATION_NAME,
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE)) if total_count else max_pages
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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = SeochoCrawler()
    print("=== 전체 조회 ===")
    results = crawler.search("", max_pages=1)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
