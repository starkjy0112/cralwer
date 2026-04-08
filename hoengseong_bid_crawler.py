# -*- coding: utf-8 -*-
"""
횡성군청 입찰공고 크롤러
https://gyeyak.hsg.go.kr/bid
실제 데이터는 hanayo.net iframe (HTML 파싱), EUC-KR, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import subprocess
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://g.hanayo.net"
LIST_URL = f"{BASE_URL}/main2024.html"
DETAIL_BASE = "https://gyeyak.hsg.go.kr/bid"
PAGE_SIZE = 10
ORGANIZATION_NAME = "횡성군청"
GCODE = "hsg"


class HoengseongBidCrawler:
    """횡성군청 입찰공고 크롤러 (계약정보공개시스템)"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": DETAIL_BASE,
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.verify = False

    def _fetch_page_curl(self, keyword, page):
        import urllib.parse
        kw_encoded = ""
        if keyword:
            try:
                kw_encoded = urllib.parse.quote(keyword.encode("euc-kr"))
            except (UnicodeEncodeError, UnicodeDecodeError):
                kw_encoded = urllib.parse.quote(keyword)

        params = {
            "gcode": GCODE,
            "type": "bid",
            "btype": "0",
            "page": str(page),
            "keyword": kw_encoded,
            "keywordIdx": "1",
            "bt": "",
            "wday1": "",
            "wday2": "",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{LIST_URL}?{query}"

        try:
            result = subprocess.run(
                ["curl", "-sk", "--max-time", "45", url,
                 "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                 "-H", f"Referer: {DETAIL_BASE}"],
                capture_output=True, timeout=50,
            )
            return result.stdout
        except (subprocess.TimeoutExpired, Exception):
            return b""

    def _fetch_page(self, keyword, page):
        raw = self._fetch_page_curl(keyword, page)
        if not raw:
            return [], 0

        text = raw.decode("euc-kr", errors="replace")
        soup = BeautifulSoup(text, "lxml")

        total_count = 0
        last_page_link = soup.select_one("#PageList a.last_page")
        if last_page_link:
            href = last_page_link.get("href", "")
            m = re.search(r'page=(\d+)', href)
            if m:
                total_count = int(m.group(1)) * PAGE_SIZE
        else:
            page_div = soup.select_one("#PageList")
            if page_div:
                max_page = 1
                for link in page_div.select("a"):
                    m = re.search(r'page=(\d+)', link.get("href", ""))
                    if m:
                        max_page = max(max_page, int(m.group(1)))
                if max_page > 1:
                    total_count = max_page * PAGE_SIZE
                else:
                    selected = page_div.select_one(".selectedPage")
                    if selected:
                        total_count = PAGE_SIZE

        items = []
        rows = soup.select("ul.ul-body")
        for row in rows:
            cat_el = row.select_one("li.category2")
            category = cat_el.get_text(strip=True) if cat_el else ""
            num_el = row.select_one("li.num")
            number = num_el.get_text(strip=True) if num_el else ""
            time_el = row.select_one("li.time")
            date = time_el.get_text(strip=True) if time_el else ""
            dept_el = row.select_one("li.dept")
            dept = dept_el.get_text(strip=True) if dept_el else ORGANIZATION_NAME
            name_el = row.select_one("li.name")
            if not name_el:
                continue
            link = name_el.select_one("a")
            if not link:
                continue
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            items.append({
                "number": number,
                "title": f"[{category}] {title}" if category else title,
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
        print(f"[{ORGANIZATION_NAME} 입찰공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = HoengseongBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
