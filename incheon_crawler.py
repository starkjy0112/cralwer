# -*- coding: utf-8 -*-
"""
인천광역시청 고시공고 크롤러
http://announce.incheon.go.kr/citynet/jsp/sap/SAPGosiBizProcess.do
CityNet 레거시 BBS, POST 방식, 10건/페이지
주의: 페이지는 charset=euc-kr 선언이지만 실제 응답은 UTF-8
     키워드 검색 시 EUC-KR 인코딩 필요
"""
import math
import re
from datetime import datetime, timedelta
import urllib.parse
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "http://announce.incheon.go.kr"
LIST_URL = f"{BASE_URL}/citynet/jsp/sap/SAPGosiBizProcess.do"
PAGE_SIZE = 10


class IncheonCrawler:
    """인천광역시청 고시공고 크롤러"""

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

    def _fetch_page(self, keyword, page, start_date=None, end_date=None):
        url = (
            f"{LIST_URL}?command=searchList"
            f"&flag=gosiGL&svp=Y&sido=ic"
        )

        # CityNet은 EUC-KR 인코딩된 폼 데이터를 기대함
        fields = {
            "currPageNo": str(page),
            "flag": "gosiGL",
            "sno": "",
            "gosiGbn": "",
            "conDeptCode": "",
            "conIfmStdt": start_date if start_date else "2024-01-01",
            "conIfmStdt_Date": start_date.replace("-", "") if start_date else "20240101",
            "conIfmEnddt": end_date if end_date else "2026-12-31",
            "conIfmEnddt_Date": end_date.replace("-", "") if end_date else "20261231",
            "conAnnounceNo": "",
            "conGosiGbn": "",
            "conDeptNm": "",
            "conTitle": keyword if keyword else "",
            "appCode": "",
            "rescCode": "",
        }

        # 키워드를 EUC-KR로 인코딩하여 전송
        parts = []
        for k, v in fields.items():
            k_enc = urllib.parse.quote(k, safe="")
            try:
                v_enc = urllib.parse.quote(v.encode("euc-kr"), safe="")
            except (UnicodeEncodeError, UnicodeDecodeError):
                v_enc = urllib.parse.quote(v, safe="")
            parts.append(f"{k_enc}={v_enc}")
        body = "&".join(parts)

        resp = self.session.post(
            url, data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        text = resp.content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(text, "lxml")

        # 총 건수: "1/375 (총 3744건)" 패턴
        total_count = 0
        m = re.search(r'총\s*(\d[\d,]*)\s*건', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
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

            # 상세 URL: onclick="viewData('65406','A')"
            onclick = row.get("onclick", "")
            m_view = re.search(r"viewData\('(\d+)','(\w+)'\)", onclick)
            if m_view:
                sno = m_view.group(1)
                gosi_gbn = m_view.group(2)
                detail_url = (
                    f"{LIST_URL}?command=searchDetail&flag=gosiGL"
                    f"&svp=Y&sido=ic&sno={sno}&gosiGbn={gosi_gbn}"
                )
            else:
                detail_url = url

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": dept if dept else "인천광역시청",
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
        print(f"[인천광역시청] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    crawler = IncheonCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
