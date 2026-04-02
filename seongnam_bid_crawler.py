# -*- coding: utf-8 -*-
"""
성남시청 입찰공고 크롤러
https://www.seongnam.go.kr/notice/publicNotice02.do?menuIdx=1000056
POST 기반(eminwon iframe), 10건/페이지
실제 데이터: https://eminwon.seongnam.go.kr/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://eminwon.seongnam.go.kr"
LIST_URL = f"{BASE_URL}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
DETAIL_BASE = f"{BASE_URL}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
PAGE_SIZE = 100
ORGANIZATION_NAME = "성남시청"


class SeongnamBidCrawler:
    """성남시청 입찰공고 크롤러"""

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
            "not_ancmt_se_code": "02",
            "title": "입찰공고",
            "countYn": "Y",
            "ofr_pageSize": str(PAGE_SIZE),
            "list_gubun": "",
        }
        if keyword:
            data["not_ancmt_sj"] = keyword
        else:
            data["not_ancmt_sj"] = ""

        resp = self.session.post(LIST_URL, data=data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # Parse total count from "전체게시물:N개" and "페이지:1/17"
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
        # Find the data table (class='bd00 bd00Bbs')
        table = soup.find("table", class_="bd00Bbs") or soup.find("table", class_="bd00")
        if not table:
            for t in soup.find_all("table"):
                rows = t.find_all("tr")
                if len(rows) > 5:
                    table = t
                    break

        if table:
            rows = table.find_all("tr")
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 6:
                    continue
                # 번호, 고시공고번호, 제목, 담당부서, 등록일, 게재기간
                number = tds[0].get_text(strip=True)
                title_td = tds[2]
                title_tag = title_td.find("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                # Extract detail ID from onclick="javascript:searchDetail('147410')"
                onclick = title_tag.get("onclick", "")
                m_id = re.search(r"searchDetail\('(\d+)'\)", onclick)
                detail_url = ""
                if m_id:
                    detail_url = (
                        f"https://www.seongnam.go.kr/notice/publicNotice02.do"
                        f"?menuIdx=1000056&not_ancmt_mgt_no={m_id.group(1)}"
                    )
                date = tds[4].get_text(strip=True)

                items.append({
                    "number": number,
                    "title": title,
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
    crawler = SeongnamBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
