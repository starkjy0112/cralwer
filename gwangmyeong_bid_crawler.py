# -*- coding: utf-8 -*-
"""
광명시청 입찰공고 크롤러
https://www.gm.go.kr/pt/user/nftcBbs/BD_selectNftcBbsList.do?q_nftcBbsCode=1003
GET 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gm.go.kr"
LIST_URL = f"{BASE_URL}/pt/user/nftcBbs/BD_selectNftcBbsList.do"
DETAIL_URL = f"{BASE_URL}/pt/user/nftcBbs/BD_selectNftcBbsDetail.do"
PAGE_SIZE = 100
ORGANIZATION_NAME = "광명시청"


class GwangmyeongBidCrawler:
    """광명시청 입찰공고 크롤러"""

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
            "q_nftcBbsCode": "1003",
            "q_currPage": str(page),
            "q_rowPerPage": str(PAGE_SIZE),
        }
        if keyword:
            params["q_searchKeyTy"] = "1001"
            params["q_searchVal"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # Parse total count from "총 게시물 : <span>3183</span>개"
        total_count = 0
        total_msg = soup.find("div", class_="total_msg")
        if total_msg:
            span = total_msg.find("span")
            if span:
                try:
                    total_count = int(re.sub(r"[^\d]", "", span.get_text(strip=True)))
                except ValueError:
                    pass

        items = []
        table = soup.find("table", class_="table_style2")
        if not table:
            table = soup.find("table", class_="bbsList")
        if table:
            tbody = table.find("tbody")
            if tbody:
                rows = tbody.find_all("tr")
                for tr in rows:
                    tds = tr.find_all("td")
                    if len(tds) < 6:
                        continue
                    number = tds[0].get_text(strip=True)
                    title_td = tds[2]
                    title_tag = title_td.find("a")
                    if not title_tag:
                        continue
                    title = title_tag.get_text(strip=True)
                    # Extract mgtno from onclick="opDetail('65851')"
                    onclick = title_tag.get("onclick", "")
                    m = re.search(r"opDetail\('(\d+)'\)", onclick)
                    mgtno = m.group(1) if m else ""
                    detail_url = f"{DETAIL_URL}?q_nftcBbsCode=1003&q_nftcBbsMgtno={mgtno}" if mgtno else ""
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
    crawler = GwangmyeongBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
