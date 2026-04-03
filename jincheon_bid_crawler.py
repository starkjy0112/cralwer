# -*- coding: utf-8 -*-
"""
진천군청 입찰공고 크롤러
https://www.jincheon.go.kr/home/sub.do?menukey=236
실제 데이터는 eminwon.jincheon.go.kr OfrAction (POST, 구형 eminwon)
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

JSP_URL = "https://eminwon.jincheon.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp"
EMINWON_URL = "https://eminwon.jincheon.go.kr/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "진천군청"


class JincheonBidCrawler:
    """진천군청 입찰공고 크롤러"""

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

    def _ensure_session(self):
        if not self._initialized:
            self.session.get(JSP_URL, params={
                "not_ancmt_se_code": "02",
            }, timeout=30)
            self._initialized = True

    def _fetch_page(self, keyword, page):
        self._ensure_session()
        data = {
            "pageIndex": str(page) if page > 1 else "",
            "jndinm": "OfrNotAncmtEJB",
            "context": "NTIS",
            "method": "selectListOfrNotAncmt",
            "methodnm": "selectListOfrNotAncmtHomepage",
            "not_ancmt_mgt_no": "",
            "homepage_pbs_yn": "Y",
            "subCheck": "Y",
            "ofr_pageSize": str(PAGE_SIZE),
            "not_ancmt_se_code": "02",
            "initValue": "Y",
            "countYn": "Y",
            "not_ancmt_sj": keyword or "",
        }
        resp = self.session.post(EMINWON_URL, data=data, timeout=30)
        resp.encoding = "utf-8"

        total_count = 0
        items = []

        total_m = re.search(r"전체게시물:(\d+)개", resp.text)
        if total_m:
            total_count = int(total_m.group(1))

        soup = BeautifulSoup(resp.text, "lxml")

        # Find all elements with searchDetail onclick (can be <a> or <td>)
        all_elements = soup.find_all(["a", "td"], onclick=re.compile(r"searchDetail"))

        seen_ids = {}
        for el in all_elements:
            onclick = el.get("onclick", "")
            m = re.search(r"searchDetail\('(\d+)'\)", onclick)
            if not m:
                continue
            mgt_no = m.group(1)
            if mgt_no not in seen_ids:
                seen_ids[mgt_no] = []
            text = el.get_text(strip=True)
            if text:
                seen_ids[mgt_no].append(text)

        for mgt_no, texts in seen_ids.items():
            texts = [t for t in texts if t]
            if len(texts) < 4:
                continue

            number = ""
            gosi_no = ""
            title_text = ""
            dept = ""
            date = ""

            for t in texts:
                if re.match(r"^\d+$", t) and not number:
                    number = t
                elif ("공고" in t or "고시" in t) and "제" in t and len(t) < 40:
                    gosi_no = t
                elif re.match(r"\d{4}-\d{2}-\d{2}", t):
                    date = t
                elif len(t) > 10 and not title_text:
                    title_text = t
                elif len(t) < 15 and not dept and not t.isdigit():
                    dept = t

            if not title_text and len(texts) >= 3:
                title_text = max(texts[1:], key=len) if len(texts) > 1 else texts[0]
            if not date:
                for t in texts:
                    if re.match(r"\d{4}-\d{2}-\d{2}", t):
                        date = t
                        break

            title = f"[{gosi_no}] {title_text}" if gosi_no else title_text
            detail_url = (
                f"{EMINWON_URL}?jndinm=OfrNotAncmtEJB&context=NTIS"
                f"&method=selectOfrNotAncmt&methodnm=selectOfrNotAncmtRegst"
                f"&not_ancmt_mgt_no={mgt_no}"
            )

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": f"{ORGANIZATION_NAME} ({dept})" if dept else ORGANIZATION_NAME,
            })

        items.sort(key=lambda x: x.get("number", "0"), reverse=True)
        return items, total_count

    WORKERS = 50

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
        print(f"[{ORGANIZATION_NAME} 입찰공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = JincheonBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n=== '용역' 검색 ===")
    results2 = crawler.search("용역", max_pages=1)
    for r in results2[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n공고: {len(results)}건, 용역: {len(results2)}건")
