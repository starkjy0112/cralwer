# -*- coding: utf-8 -*-
"""
시흥시청 고시/공고 크롤러
https://www.siheung.go.kr/main/saeol/gosi/list.do?mId=0401040100
POST 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.siheung.go.kr"
LIST_URL = f"{BASE_URL}/main/saeol/gosi/list.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "시흥시청"


class SiheungGosiCrawler:
    """시흥시청 고시/공고 크롤러"""

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
        data = {
            "mId": "0401040100",
            "page": str(page),
        }
        if keyword:
            data["searchType"] = "tit"
            data["searchTxt"] = keyword

        resp = self.session.post(LIST_URL, data=data, params={"mId": "0401040100"}, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # Parse total pages from "현재 페이지 1 / 전체 페이지 N"
        total_count = 0
        page_num = soup.find("p", class_="page_num") or soup.find("span", class_="page_num")
        if page_num:
            m = re.search(r"전체\s*페이지\s*(\d+)", page_num.get_text())
            if m:
                total_count = int(m.group(1)) * PAGE_SIZE
        if not total_count:
            text = soup.get_text()
            m = re.search(r'총\s*([\d,]+)\s*건', text)
            if m:
                total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.find("table", class_="bod_list")
        if not table:
            for t in soup.find_all("table"):
                rows = t.find_all("tr")
                if 5 < len(rows) < 25:
                    table = t
                    break

        if table:
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 5:
                    continue
                number = tds[0].get_text(strip=True)
                title_td = tds[2]
                title_tag = title_td.find("a")
                if not title_tag:
                    continue
                for ico in title_tag.find_all("span", class_="ico_new"):
                    ico.decompose()
                title = title_tag.get_text(strip=True)
                data_action = title_tag.get("data-action", "")
                href = title_tag.get("href", "")
                if data_action:
                    detail_url = BASE_URL + data_action
                elif href and href != "#" and not href.startswith("javascript"):
                    detail_url = f"{BASE_URL}{href}" if href.startswith("/") else href
                else:
                    detail_url = ""
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
    crawler = SiheungGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
