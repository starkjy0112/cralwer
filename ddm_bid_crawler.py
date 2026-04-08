# -*- coding: utf-8 -*-
"""
동대문구청 입찰공고 크롤러 (서울계약마당 iframe)
https://www.ddm.go.kr/www/contents.do?key=169
→ contract.seoul.go.kr pubBidInfo.do (ps1_searchTxt=동대문구)
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from datetime import datetime
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://contract.seoul.go.kr"
LIST_URL = f"{BASE_URL}/new1/views/pubBidInfo.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "동대문구청"


class DdmBidCrawler:
    """동대문구청 입찰공고 크롤러 (서울계약마당)"""

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _fetch_page(self, keyword, page):
        params = {
            "ps_selectForm": "1",
            "ps_recordCountPerPage": str(PAGE_SIZE),
            "ps1_fisYear": str(datetime.now().year),
            "ps1_selectSearch": "2",
            "ps1_searchTxt": "동대문구",
            "ps_currentPageNo": str(page),
        }

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

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
                m_bid = re.search(r"bidPopup_getBidInfoDtlUrl\(\s*'(\d+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'(\d+)'\s*\)", onclick)
                if m_bid:
                    bid_no = m_bid.group(2)
                    bid_seq = m_bid.group(3)
                    detail_url = f"{BASE_URL}/new1/views/pubBidInfoDtl.do?bidNo={bid_no}&bidSeq={bid_seq}"
            date = ""
            for td in row_date.find_all("td"):
                m_d = re.search(r"(\d{4}-\d{2}-\d{2})", td.get_text(strip=True))
                if m_d:
                    date = m_d.group(1)
                    break
            items.append({"number": bid_no, "title": title, "date": date, "url": detail_url, "organization": ORGANIZATION_NAME})

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")
        if actual_pages <= 1:
            all_items = first_items
        else:
            page_results = {1: first_items}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {executor.submit(self._fetch_page, keyword, p): p for p in range(2, actual_pages + 1)}
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
        if keyword:
            all_items = [item for item in all_items if keyword in item["title"]]
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
