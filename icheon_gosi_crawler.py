# -*- coding: utf-8 -*-
"""
이천시청 일반공고 크롤러
https://www.icheon.go.kr/portal/saeol/gosi/list.do?seCode=04&mid=0402020000
POST 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.icheon.go.kr"
LIST_URL = f"{BASE_URL}/portal/saeol/gosi/list.do"
MID = "0402020000"
PAGE_SIZE = 100


class IcheonGosiCrawler:
    """이천시청 일반공고 크롤러"""

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
        data = {
            "page": str(page),
            "pageSize": str(PAGE_SIZE),
            "seCode": "04",
        }
        if keyword:
            data["searchType"] = "NOT_ANCMT_SJ"
            data["searchTxt"] = keyword

        resp = self.session.post(
            f"{LIST_URL}?mid={MID}", data=data, timeout=15
        )
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []

        table = soup.select_one("table.bod_list")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 5:
                continue

            number = row.select_one("td.list_num")
            number = number.get_text(strip=True) if number else tds[0].get_text(strip=True)

            if total_count == 0 and page == 1 and number.isdigit():
                total_count = int(number)

            notice_no = tds[1].get_text(strip=True)

            title_td = row.select_one("td.list_tit")
            if not title_td:
                title_td = tds[2]
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
                detail_url = f"{LIST_URL}?mid={MID}"

            dept_td = row.select_one("td.list_dept")
            dept = dept_td.get_text(strip=True) if dept_td else ""

            date_td = row.select_one("td.list_date")
            date = date_td.get_text(strip=True) if date_td else ""

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "이천시청",
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
        print(f"[이천시청 일반공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    crawler = IcheonGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
