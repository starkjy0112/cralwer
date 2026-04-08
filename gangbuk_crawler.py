# -*- coding: utf-8 -*-
"""
강북구청 고시/공고 크롤러
https://www.gangbuk.go.kr/portal/bbs/B0000245/list.do?menuNo=200082
GET 기반, 10건/페이지 (WAF 쿠키 처리 필요)
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gangbuk.go.kr"
LIST_URL = f"{BASE_URL}/portal/bbs/B0000245/list.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "강북구청"
BBS_ID = "B0000245"
MENU_NO = "200082"


class GangbukCrawler:
    """강북구청 고시/공고 크롤러"""

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
        self._init_session()

    def _init_session(self):
        """WAF 쿠키 초기화"""
        try:
            resp = self.session.get(LIST_URL, params={"menuNo": MENU_NO}, timeout=15)
            # sabFingerPrint 쿠키 처리
            if "sabFingerPrint" in resp.text or "sabSignature" in resp.text:
                m = re.search(r"sabSignature=([^'\"]+)", resp.text)
                if m:
                    self.session.cookies.set("sabFingerPrint", "1920,1080,www.gangbuk.go.kr")
                    self.session.cookies.set("sabSignature", m.group(1))
                    self.session.get(LIST_URL, params={"menuNo": MENU_NO}, timeout=15)
        except Exception:
            pass

    def _fetch_page(self, keyword, page):
        params = {
            "menuNo": MENU_NO,
            "pageIndex": str(page),
        }
        if keyword:
            params["searchCnd"] = "1"
            params["searchWrd"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        # 총 건수: "총 XX건"
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
                if len(tds) < 5:
                    continue
                number = tds[0].get_text(strip=True)
                if not total_count and number.replace(",", "").isdigit():
                    total_count = int(number.replace(",", ""))

                title_td = tds[2] if len(tds) > 2 else tds[1]
                title_tag = title_td.find("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                detail_url = BASE_URL + href if href and not href.startswith("http") else href

                # 날짜 열 (마지막 열 or 4번째)
                raw_date = tds[-1].get_text(strip=True) if len(tds) >= 5 else ""
                date = raw_date.split("~")[0].strip().replace(".", "-") if raw_date else ""
                # 날짜 열이 숫자가 아닌 경우 다른 열 탐색
                if not re.search(r"\d{4}", date):
                    for td in reversed(tds):
                        txt = td.get_text(strip=True)
                        if re.search(r"\d{4}[-./]\d{2}[-./]\d{2}", txt):
                            date = txt
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
            paging = soup.find("div", class_="paginationSet") or soup.find("div", class_="pagination")
            if paging:
                max_page = 1
                for a in paging.find_all("a"):
                    href = a.get("href", "")
                    m_p = re.search(r"pageIndex=(\d+)", href)
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
    crawler = GangbukCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
