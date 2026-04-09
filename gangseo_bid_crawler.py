# -*- coding: utf-8 -*-
"""
강서구청 입찰공고 크롤러 (서울계약마당 iframe)
https://www.gangseo.seoul.kr/gs030506
→ contract.seoul.go.kr iframe (s_SET_OFFICE_CD=4600)
GET 기반, 10건/페이지, 3행=1건 구조
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://contract.seoul.go.kr"
LIST_URL = f"{BASE_URL}/new1/views/pubBidInfo.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "강서구청"
OFFICE_CD = "4600"


class GangseoBidCrawler:
    """강서구청 입찰공고 크롤러 (서울계약마당)"""

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
        params = {
            "ps_frame": "true",
            "ps_t2OfficeCd": "4",
            "ps_setOfficeCd": OFFICE_CD,
            "ps_firstPage": "" if page > 1 else "S",
            "ps_selectForm": "0",
            "ps_currentPageNo": str(page),
            "ps_recordCountPerPage": str(PAGE_SIZE),
        }
        if keyword:
            params["ps_selectForm"] = "1"
            params["ps1_fisYear"] = str(datetime.now().year)
            params["ps1_selectSearch"] = "1"
            params["ps1_searchTxt"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수
        total_count = 0
        m = re.search(r"총\s*([\d,]+)\s*건", resp.text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        tbody = soup.find("tbody")
        if not tbody:
            return items, total_count

        rows = tbody.find_all("tr")
        i = 0
        while i + 2 < len(rows):
            row_meta = rows[i]
            row_title = rows[i + 1]
            row_date = rows[i + 2]
            i += 3

            meta_td = row_meta.find("td", class_="settxt")
            if not meta_td:
                continue

            title_td = row_title.find("td", class_="setst")
            if not title_td:
                continue
            link = title_td.find("a")
            title = link.get_text(strip=True) if link else title_td.get_text(strip=True)

            detail_url = LIST_URL
            bid_no = ""
            if link:
                onclick = link.get("onclick", "")
                m_bid = re.search(
                    r"bidPopup_getBidInfoDtlUrl\(\s*'(\d+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'(\d+)'\s*\)",
                    onclick,
                )
                if m_bid:
                    bid_id = m_bid.group(2)
                    bid_seq = m_bid.group(3)
                    bid_no = bid_id
                    detail_url = f"{BASE_URL}/new1/views/pubBidInfoDtl.do?bidNo={bid_id}&bidSeq={bid_seq}"

            date = ""
            date_tds = row_date.find_all("td")
            for td in date_tds:
                text = td.get_text(strip=True)
                m_d = re.search(r"(\d{4}-\d{2}-\d{2})", text)
                if m_d:
                    date = m_d.group(1)
                    break

            items.append({
                "number": bid_no,
                "title": title,
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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GangseoBidCrawler()
    print("=== 전체 조회 ===")
    results = crawler.search("", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
