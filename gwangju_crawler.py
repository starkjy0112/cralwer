# -*- coding: utf-8 -*-
"""
광주광역시청 고시공고 크롤러
https://www.gwangju.go.kr/contentsView.do?pageId=www791
실제 데이터는 iframe 내 별도 서버에서 제공:
https://sido.gwangju.go.kr/citynet/jsp/sap/SAPGosiBizProcess.do
POST 기반, 10건/페이지, currPageNo 방식, euc-kr 인코딩
"""
import math
import re
from urllib.parse import quote
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


IFRAME_BASE = "https://sido.gwangju.go.kr"
LIST_URL = f"{IFRAME_BASE}/citynet/jsp/sap/SAPGosiBizProcess.do"
PAGE_SIZE = 10


class GwangjuCrawler:
    """광주광역시청 고시공고 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.gwangju.go.kr/contentsView.do?pageId=www791",
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _fetch_page(self, keyword, page, start_date=None, end_date=None):
        params = {
            "command": "searchList",
            "flag": "gosiGL",
            "svp": "Y",
            "sido": "",
        }
        post_data = {
            "appCode": "",
            "rescCode": "",
            "sno": "",
            "flag": "gosiGL",
            "gosiGbn": "",
            "currPageNo": str(page),
            "conDeptCode": "",
            "conIfmStdt": start_date if start_date else "",
            "conIfmStdt_Date": start_date.replace("-", "") if start_date else "",
            "conIfmEnddt": end_date if end_date else "",
            "conIfmEnddt_Date": end_date.replace("-", "") if end_date else "",
            "conAnnounceNo": "",
            "conGosiGbn": "",
            "conDeptNm": "",
        }
        if keyword:
            post_data["conTitle"] = keyword

        # 서버가 euc-kr 인코딩 form을 요구 (accept-charset="euc-kr")
        # POST body를 euc-kr로 인코딩하되 응답은 utf-8로 디코딩
        encoded_body = "&".join(
            f"{k}={quote(v, encoding='euc-kr', safe='')}" for k, v in post_data.items()
        )
        resp = self.session.post(
            LIST_URL,
            params=params,
            data=encoded_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: "1/201 (총 2007건)"
        total_count = 0
        tds = soup.select("td")
        for td in tds:
            text = td.get_text(strip=True)
            m = re.search(r'총\s*(\d[\d,]*)\s*건', text)
            if m:
                total_count = int(m.group(1).replace(",", ""))
                break

        items = []
        # 데이터 테이블은 toolBoardList 클래스
        table = soup.select_one("table.toolBoardList")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            title = cells[1].get_text(strip=True)
            dept = cells[2].get_text(strip=True)
            date = cells[3].get_text(strip=True)

            # onclick="viewData('36101','A')" 에서 sno, gosiGbn 추출
            onclick = row.get("onclick", "")
            m = re.search(r"viewData\('(\d+)',\s*'([^']+)'\)", onclick)
            if m:
                sno = m.group(1)
                gosi_gbn = m.group(2)
                detail_url = (
                    f"{LIST_URL}?command=searchDetail&flag=gosiGL"
                    f"&svp=Y&sido=&sno={sno}&gosiGbn={gosi_gbn}"
                )
            else:
                detail_url = "https://www.gwangju.go.kr/contentsView.do?pageId=www791"

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": dept if dept else "광주광역시청",
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        first_items, total_count = self._fetch_page(keyword, 1, start_date, end_date)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        if actual_pages <= 1:
            all_items = first_items
        else:
            page_results = {1: first_items}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_page, keyword, p, start_date, end_date): p
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
        print(f"[광주광역시청] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GwangjuCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
