# -*- coding: utf-8 -*-
"""
노원구청 고시공고 크롤러
https://www.nowon.kr/www/user/bbs/BD_selectBbsList.do?q_bbsCode=1003&q_clCode=0&q_estnColumn1=11&q_ntceSiteCode=11
GET 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.nowon.kr"
LIST_URL = f"{BASE_URL}/www/user/bbs/BD_selectBbsList.do"
DETAIL_URL = f"{BASE_URL}/www/user/bbs/BD_selectBbs.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "노원구청"


class NowonCrawler:
    """노원구청 고시공고 크롤러"""

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
            "q_bbsCode": "1003",
            "q_clCode": "0",
            "q_estnColumn1": "11",
            "q_ntceSiteCode": "11",
            "q_currPage": str(page),
            "q_pClCode": "0",
        }
        if keyword:
            params["q_searchKeyTy"] = "sj___1002"
            params["q_searchVal"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        # "총 XXX건"
        m = re.search(r"총\s*([\d,]+)\s*건", soup.get_text())
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        table = None
        for t in soup.find_all("table"):
            rows = t.find_all("tr")
            if len(rows) > 3:
                table = t
                break

        if table:
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 4:
                    continue
                number = tds[0].get_text(strip=True)
                if not total_count and number.replace(",", "").isdigit():
                    total_count = int(number.replace(",", ""))

                # 제목 열 탐색 (보통 2~3번째 td)
                title_tag = None
                title_td = None
                for td in tds:
                    a = td.find("a")
                    if a and len(a.get_text(strip=True)) > 5:
                        title_tag = a
                        title_td = td
                        break

                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                detail_url = BASE_URL + href if href and not href.startswith("http") else href

                # 날짜 열
                date = ""
                for td in reversed(tds):
                    txt = td.get_text(strip=True)
                    m_d = re.search(r"\d{4}[-./]\d{2}[-./]\d{2}", txt)
                    if m_d:
                        date = m_d.group(0).replace(".", "-").replace("/", "-")
                        break

                items.append({
                    "number": number,
                    "title": title,
                    "date": date,
                    "url": detail_url,
                    "organization": ORGANIZATION_NAME,
                })

        # 페이지네이션 추정
        if not total_count:
            paging = soup.find("div", class_=lambda c: c and "paging" in str(c).lower())
            if paging:
                max_page = 1
                for a in paging.find_all("a"):
                    href = a.get("href", "")
                    m_p = re.search(r"q_currPage=(\d+)", href)
                    if m_p:
                        pn = int(m_p.group(1))
                        if pn > max_page:
                            max_page = pn
                total_count = max_page * PAGE_SIZE

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
    crawler = NowonCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
