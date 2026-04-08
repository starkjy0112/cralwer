# -*- coding: utf-8 -*-
"""
전라남도청 입찰공고 크롤러
https://gyeyak.jeonnam.go.kr/bid
실제 데이터는 hanayo.net iframe (HTML 파싱), EUC-KR, 10건/페이지
hanayo.net 서버가 느리므로 subprocess curl 사용
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
DETAIL_BASE = "https://gyeyak.jeonnam.go.kr/bid"
PAGE_SIZE = 10


class JeonnamBidCrawler:
    """전라남도청 입찰공고 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://gyeyak.jeonnam.go.kr/bid",
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.verify = False

    def _fetch_page_curl(self, keyword, page):
        """curl을 사용하여 페이지를 가져옴 (hanayo.net 서버 호환성)"""
        import urllib.parse
        # hanayo.net은 EUC-KR 인코딩 키워드를 기대함
        kw_encoded = ""
        if keyword:
            try:
                kw_encoded = urllib.parse.quote(keyword.encode("euc-kr"))
            except (UnicodeEncodeError, UnicodeDecodeError):
                kw_encoded = urllib.parse.quote(keyword)

        params = {
            "gcode": "jeonnam",
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
                 "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"],
                capture_output=True, timeout=50,
            )
            return result.stdout
        except (subprocess.TimeoutExpired, Exception):
            return b""

    def _fetch_page(self, keyword, page):
        raw = self._fetch_page_curl(keyword, page)
        if not raw:
            return [], 0

        # hanayo.net은 EUC-KR 인코딩
        text = raw.decode("euc-kr", errors="replace")
        soup = BeautifulSoup(text, "lxml")

        # 총 페이지 수: 마지막 페이지 링크에서 추출
        total_count = 0
        last_page_link = soup.select_one("#PageList a.last_page")
        if last_page_link:
            href = last_page_link.get("href", "")
            m = re.search(r'page=(\d+)', href)
            if m:
                total_count = int(m.group(1)) * PAGE_SIZE
        else:
            # 페이지 링크에서 최대 페이지 추출
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
                    # 선택된 페이지만 있는 경우
                    selected = page_div.select_one(".selectedPage")
                    if selected:
                        total_count = PAGE_SIZE

        items = []
        rows = soup.select("ul.ul-body")
        for row in rows:
            # 카테고리 (공사/용역/물품)
            cat_el = row.select_one("li.category2")
            category = cat_el.get_text(strip=True) if cat_el else ""

            # 입찰번호
            num_el = row.select_one("li.num")
            number = num_el.get_text(strip=True) if num_el else ""

            # 마감일시
            time_el = row.select_one("li.time")
            date = time_el.get_text(strip=True) if time_el else ""

            # 발주기관
            dept_el = row.select_one("li.dept")
            dept = dept_el.get_text(strip=True) if dept_el else "전라남도청"

            # 제목 및 링크
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
                "organization": dept if dept else "전라남도청",
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 약 {total_count}건)")

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
        print(f"[전라남도청] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    crawler = JeonnamBidCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공사' 검색 ===")
    results2 = crawler.search("공사", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
