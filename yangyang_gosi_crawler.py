# -*- coding: utf-8 -*-
"""
양양군청 공고/고시 크롤러
https://www.yangyang.go.kr/gw/portal/yyc_news_notifi
iframe -> eminwon.yangyang.go.kr POST 기반, EUC-KR, 10건/페이지
"""
import math
import re
import time
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://eminwon.yangyang.go.kr"
ACTION_URL = f"{BASE_URL}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
DETAIL_BASE = f"{BASE_URL}/emwp/jsp/ofr/OfrNotAncmtVSub.jsp"
PAGE_SIZE = 10
ORGANIZATION_NAME = "양양군청"
SE_CODE = "01,04,05,06"


class YangyangGosiCrawler:
    """양양군청 공고/고시 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": f"{BASE_URL}/emwp/jsp/ofr/OfrNotAncmtLSub.jsp",
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.verify = False

    def _fetch_page(self, keyword, page):
        data = {
            "jndinm": "OfrNotAncmtEJB",
            "context": "NTIS",
            "method": "selectListOfrNotAncmt",
            "methodnm": "selectListOfrNotAncmtHomepage",
            "not_ancmt_se_code": SE_CODE,
            "homepage_pbs_yn": "Y",
            "subCheck": "Y",
            "ofr_pageSize": str(PAGE_SIZE),
            "countYn": "Y",
            "pageIndex": str(page) if page > 1 else "",
            "epcCheck": "",
            "not_ancmt_mgt_no": "",
            "not_ancmt_sj": keyword if keyword else "",
            "not_ancmt_cn": "",
            "dept_nm": "",
            "not_ancmt_reg_no": "",
            "temp": "",
            "recent_mm": "",
            "yyyy": "",
            "yyyymmdd": "",
        }

        resp = None
        last_err = None
        for attempt in range(3):
            try:
                resp = self.session.post(ACTION_URL, data=data, timeout=30)
                break
            except Exception as e:
                last_err = e
                time.sleep(1 * (attempt + 1))
        if resp is None:
            return [], 0
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        text = soup.get_text()
        m = re.search(r'(\d[\d,]*)\s*건', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))
        if not total_count:
            m2 = re.search(r'(\d+)/(\d+)', text)
            if m2:
                total_count = int(m2.group(2)) * PAGE_SIZE

        items = []
        table = soup.select_one("table.skinTb")
        if not table:
            for t in soup.find_all("table"):
                rows = t.find_all("tr")
                if len(rows) > 3:
                    table = t
                    break
        if not table:
            return items, total_count

        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            number = tds[0].get_text(strip=True)
            gosi_no = tds[1].get_text(strip=True) if len(tds) > 5 else ""
            title_idx = 2 if len(tds) > 5 else 1
            a_tag = tds[title_idx].find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            onclick = a_tag.get("onclick", "")
            mgt_match = re.search(r"searchDetail\('(\d+)'\)", onclick)
            if mgt_match:
                detail_url = f"{DETAIL_BASE}?not_ancmt_mgt_no={mgt_match.group(1)}"
            else:
                detail_url = f"https://www.yangyang.go.kr/gw/portal/yyc_news_notifi"
            dept_idx = 3 if len(tds) > 5 else 2
            dept = tds[dept_idx].get_text(strip=True)
            date_idx = 4 if len(tds) > 5 else 3
            date_str = tds[date_idx].get_text(strip=True)

            items.append({
                "number": number,
                "title": f"[{gosi_no}] {title}" if gosi_no else title,
                "date": date_str,
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
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = YangyangGosiCrawler()
    print("=== 전체 조회 ===")
    results = crawler.search("", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
