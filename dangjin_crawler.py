# -*- coding: utf-8 -*-
"""
당진시청 고시/공고 크롤러
https://www.dangjin.go.kr/prog/publicNotice/kor/sub03_02_01_04/list.do
POST 기반, pageIndex/searchKeyword/submitTy/_csrf 검색, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.dangjin.go.kr"
LIST_URL = f"{BASE_URL}/prog/publicNotice/kor/sub03_02_01_04/list.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "당진시청"


class DangjinCrawler:
    """당진시청 고시/공고 크롤러"""

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
        self._csrf = None

    def _get_csrf(self):
        """CSRF 토큰 획득 (초기 페이지 로드)"""
        if self._csrf:
            return self._csrf
        resp = self.session.get(LIST_URL, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        meta = soup.find("meta", attrs={"name": "_csrf"})
        if meta:
            self._csrf = meta.get("content", "")
        return self._csrf or ""

    def _fetch_page(self, keyword, page):
        csrf = self._get_csrf()
        data = {
            "pageIndex": str(page),
            "_csrf": csrf,
        }
        if keyword:
            data["searchCondition"] = "not_ancmt_sj"
            data["searchKeyword"] = keyword

        resp = self.session.post(LIST_URL, data=data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 새 CSRF 갱신
        meta = soup.find("meta", attrs={"name": "_csrf"})
        if meta:
            self._csrf = meta.get("content", "")

        total_count = 0
        items = []
        # 첫 번째 테이블이 게시판 목록
        tables = soup.find_all("table")
        table = tables[0] if tables else None
        if table:
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 6:
                    continue
                gosi_no = tds[0].get_text(strip=True)
                category = tds[1].get_text(strip=True)
                title_td = tds[2]
                title_tag = title_td.find("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                if href and href.startswith("/"):
                    detail_url = BASE_URL + href
                else:
                    detail_url = href
                dept = tds[3].get_text(strip=True)
                date = tds[4].get_text(strip=True)

                items.append({
                    "number": gosi_no,
                    "title": f"[{category}] {title}" if category else title,
                    "date": date,
                    "url": detail_url,
                    "organization": ORGANIZATION_NAME,
                })

            # 페이지네이션에서 마지막 페이지 찾기 (linkPage(164) 패턴)
            if not total_count:
                max_page = 1
                for a in soup.find_all("a"):
                    onclick = a.get("onclick", "")
                    nums = re.findall(r"linkPage\(\s*(\d+)\s*\)", onclick)
                    for n in nums:
                        if int(n) > max_page:
                            max_page = int(n)
                if max_page > 1:
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
    crawler = DangjinCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
