# -*- coding: utf-8 -*-
"""
포항시청 고시공고 크롤러
https://www.pohang.go.kr/portal/saeol/gosi/list.do?mid=0202010000
POST 기반, 10건/페이지, bod_list, data-action 링크
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.pohang.go.kr"
LIST_URL = f"{BASE_URL}/portal/saeol/gosi/list.do"
MID = "0202010000"
PAGE_SIZE = 10
ORGANIZATION_NAME = "포항시청"


class PohangGosiCrawler:
    """포항시청 고시공고 크롤러"""

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
            "page": str(page),
            "seCode": "01",
        }
        if keyword:
            data["searchType"] = "tit"
            data["searchTxt"] = keyword

        resp = self.session.post(
            f"{LIST_URL}?mid={MID}", data=data, timeout=15
        )
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        if not keyword:
            page_num = soup.find("p", class_="page_num")
            if page_num:
                m = re.search(r"전체\s*페이지\s*([\d,]+)", page_num.get_text())
                if m:
                    total_count = int(m.group(1).replace(",", "")) * PAGE_SIZE

        items = []
        table = soup.select_one("table.bod_list")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 4:
                continue

            number = row.select_one("td.list_num")
            number = number.get_text(strip=True) if number else tds[0].get_text(strip=True)

            if total_count == 0 and page == 1 and number.replace(",", "").isdigit():
                total_count = int(number.replace(",", ""))

            title_td = row.select_one("td.list_tit") or row.select_one("td.taL")
            if not title_td:
                for td in tds:
                    if td.find("a"):
                        title_td = td
                        break
            if not title_td:
                continue
            link = title_td.find("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            for img in link.select("img"):
                alt = img.get("alt", "")
                title = title.replace(alt, "").strip()

            data_action = link.get("data-action", "")
            if data_action:
                detail_url = f"{BASE_URL}{data_action}"
            else:
                href = link.get("href", "")
                if href and href.startswith("/"):
                    detail_url = f"{BASE_URL}{href}"
                else:
                    detail_url = ""

            date_td = row.select_one("td.list_date")
            date = date_td.get_text(strip=True) if date_td else ""

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
        print(f"[{ORGANIZATION_NAME} 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = PohangGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
