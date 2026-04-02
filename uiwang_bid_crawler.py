# -*- coding: utf-8 -*-
"""
의왕시청 입찰정보 크롤러
https://www.uiwang.go.kr/UWKORINFO0901
e-minwon iframe 기반 (eminwon.uiwang.go.kr), not_ancmt_se_code=02, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


EMINWON_URL = "https://eminwon.uiwang.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp"
DETAIL_BASE = "https://eminwon.uiwang.go.kr/emwp/jsp/ofr/OfrNotAncmtD.jsp"
PAGE_SIZE = 100


class UiwangBidCrawler:
    """의왕시청 입찰정보 크롤러"""

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

    def _fetch_page(self, keyword, page):
        params = {
            "not_ancmt_se_code": "02",
            "list_gubun": "A",
            "epcCheck": "Y",
            "pageIndex": str(page),
            "ofr_pageSize": str(PAGE_SIZE),
            "jndinm": "OfrNotAncmtEJB",
            "context": "NTIS",
            "homepage_pbs_yn": "Y",
            "countYn": "Y",
        }
        if keyword:
            params["cha_sbjt"] = keyword

        resp = self.session.get(EMINWON_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: "전체게시물:N개"
        total_count = 0
        text = soup.get_text()
        m = re.search(r'전체게시물\s*:\s*(\d[\d,]*)\s*개', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        # 테이블: 번호, 고시공고번호, 제목, 담당부서, 등록일, 게재기간, 조회수
        for table in soup.find_all("table"):
            ths = table.find_all("th")
            headers = [th.get_text(strip=True) for th in ths]
            if "제목" in headers and "등록일" in headers:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 5:
                        continue

                    number = cells[0].get_text(strip=True)
                    notice_no = cells[1].get_text(strip=True)
                    title_cell = cells[2]
                    dept = cells[3].get_text(strip=True)
                    date = cells[4].get_text(strip=True)

                    link = title_cell.find("a")
                    if not link:
                        continue

                    title = link.get_text(strip=True)
                    onclick = link.get("onclick", "")
                    m_view = re.search(r"fn_detail\('([^']+)'\)", onclick)
                    if m_view:
                        detail_url = f"{DETAIL_BASE}?not_ancmt_mgt_no={m_view.group(1)}&not_ancmt_se_code=02"
                    else:
                        detail_url = "https://www.uiwang.go.kr/UWKORINFO0901"

                    items.append({
                        "number": number,
                        "title": title,
                        "date": date,
                        "url": detail_url,
                        "organization": "의왕시청",
                    })
                break

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
        print(f"[의왕시청 입찰정보] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = UiwangBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
