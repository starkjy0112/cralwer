# -*- coding: utf-8 -*-
"""
태백시청 입찰공고 크롤러
http://ehojo.taebaek.go.kr/bid
iframe 기반 (hanayo.net), 본문 페이지 스크래핑
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "http://ehojo.taebaek.go.kr"
LIST_URL = f"{BASE_URL}/bid"
IFRAME_BASE = "http://g.hanayo.net"
PAGE_SIZE = 10
ORGANIZATION_NAME = "태백시청"


class TaebaekBidCrawler:
    """태백시청 입찰공고 크롤러 (ehojo 계약정보공개시스템)"""

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
        """hanayo iframe API 호출"""
        params = {
            "gcode": "taebaek",
            "type": "bid",
            "btype": "",
            "page": str(page),
        }
        if keyword:
            params["search"] = keyword

        items = []
        total_count = 0

        try:
            resp = self.session.get(
                f"{IFRAME_BASE}/main2024.html",
                params=params,
                timeout=30,
            )
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")

            # hanayo 시스템은 테이블 또는 div 기반 리스트
            table = soup.select_one("table")
            if table:
                rows = table.select("tbody tr")
                if not rows:
                    rows = table.select("tr")[1:]
                for row in rows:
                    tds = row.find_all("td")
                    if len(tds) < 3:
                        continue
                    number = tds[0].get_text(strip=True)
                    if total_count == 0 and number.isdigit():
                        total_count = int(number)
                    title_td = tds[1] if len(tds) > 1 else tds[0]
                    link = title_td.find("a")
                    title = link.get_text(strip=True) if link else title_td.get_text(strip=True)
                    href = link.get("href", "") if link else ""
                    date = ""
                    for td in tds[2:]:
                        txt = td.get_text(strip=True)
                        m_date = re.search(r'(\d{4})[./-](\d{2})[./-](\d{2})', txt)
                        if m_date:
                            date = f"{m_date.group(1)}-{m_date.group(2)}-{m_date.group(3)}"
                            break
                    items.append({
                        "number": number,
                        "title": title,
                        "date": date,
                        "url": LIST_URL,
                        "organization": ORGANIZATION_NAME,
                    })
            else:
                # div 기반 리스트
                list_items = soup.select(".list-item, .bid-item, li")
                for li in list_items:
                    link = li.find("a")
                    if not link:
                        continue
                    title = link.get_text(strip=True)
                    text = li.get_text(strip=True)
                    m_date = re.search(r'(\d{4})[./-](\d{2})[./-](\d{2})', text)
                    date = f"{m_date.group(1)}-{m_date.group(2)}-{m_date.group(3)}" if m_date else ""
                    items.append({
                        "number": "",
                        "title": title,
                        "date": date,
                        "url": LIST_URL,
                        "organization": ORGANIZATION_NAME,
                    })
        except Exception:
            pass

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE)) if total_count else 1
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

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

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[{ORGANIZATION_NAME} 입찰공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = TaebaekBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
