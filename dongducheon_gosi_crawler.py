# -*- coding: utf-8 -*-
"""
동두천시청 일반공고 크롤러
https://www.ddc.go.kr/ddc/selectGosiList.do?key=340&not_ancmt_se_code=04
GET 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.ddc.go.kr"
LIST_URL = f"{BASE_URL}/ddc/selectGosiList.do"
PAGE_SIZE = 10


class DongducheonGosiCrawler:
    """동두천시청 일반공고 크롤러"""

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

    def _fetch_page(self, keyword, page):
        params = {
            "key": "340",
            "not_ancmt_se_code": "04",
            "pageIndex": str(page),
            "searchCnd": "SJ",
        }
        if keyword:
            params["searchKrwd"] = keyword
        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        em = soup.select_one(".em_black")
        if em:
            total_count = int(em.get_text(strip=True).replace(",", ""))

        items = []
        tbody = soup.select_one("table.bbs_default tbody")
        if not tbody:
            return items, total_count
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            number = tds[0].get_text(strip=True)
            gosi_no = tds[1].get_text(strip=True)
            a_tag = tds[2].find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if href.startswith("./"):
                href = f"{BASE_URL}/ddc/{href[2:]}"
            elif href.startswith("/"):
                href = f"{BASE_URL}{href}"
            dept = tds[3].get_text(strip=True)
            date = tds[4].get_text(strip=True)
            items.append({
                "number": number,
                "title": f"[{gosi_no}] {title}" if gosi_no else title,
                "date": date,
                "url": href,
                "organization": f"동두천시청 ({dept})",
            })
        return items, total_count

    WORKERS = 50

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
        print(f"[동두천시청 일반공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = DongducheonGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
