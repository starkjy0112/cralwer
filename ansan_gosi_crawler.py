# -*- coding: utf-8 -*-
"""
안산시청 고시/공고 크롤러
https://www.ansan.go.kr/www/common/bbs/selectPageListBbs.do?bbs_code=WWW13
GET 기반, 15건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.ansan.go.kr"
LIST_URL = f"{BASE_URL}/www/common/bbs/selectPageListBbs.do"
DETAIL_URL = f"{BASE_URL}/www/common/bbs/selectBbsDetail.do"
PAGE_SIZE = 15
ORGANIZATION_NAME = "안산시청"
BBS_CODE = "WWW13"


class AnsanGosiCrawler:
    """안산시청 고시/공고 크롤러"""

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
            "bbs_code": BBS_CODE,
            "key": "271",
            "currentPage": str(page),
        }
        if keyword:
            params["sch_type"] = "sj"
            params["sch_text"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # Parse total count from pagination
        total_count = 0
        paging = soup.find("div", class_="paging") or soup.find("div", class_="pagination")
        if paging:
            max_page = 1
            for a in paging.find_all("a"):
                onclick = a.get("onclick", "")
                nums = re.findall(r'fnGoPage\(\s*(\d+)\s*\)', onclick)
                for n in nums:
                    if int(n) > max_page:
                        max_page = int(n)
            total_count = max_page * PAGE_SIZE

        # Also try to get count from first td text like "14310"
        items = []
        table = None
        for t in soup.find_all("table"):
            rows = t.find_all("tr")
            if len(rows) > 5:
                table = t
                break

        if table:
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 5:
                    continue
                # 번호, 고시공고번호, 제목, 담당부서, 작성일
                number = tds[0].get_text(strip=True)
                if not total_count and number.isdigit():
                    total_count = int(number)

                title_td = tds[2]
                title_tag = title_td.find("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                # onclick="fnGoDetail( 1667009 ); return false;"
                onclick = title_tag.get("onclick", "")
                m_seq = re.search(r"fnGoDetail\(\s*(\d+)\s*\)", onclick)
                if m_seq:
                    detail_url = f"{DETAIL_URL}?bbs_code={BBS_CODE}&bbs_seq={m_seq.group(1)}"
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
    crawler = AnsanGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
