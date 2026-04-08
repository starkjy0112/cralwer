# -*- coding: utf-8 -*-
"""
대구광역시청 고시공고 크롤러
https://www.daegu.go.kr/index.do?menu_id=00940170&menu_link=/front/daeguSidoGosi/daeguSidoGosiList.do
POST 기반, 10건/페이지, pageIndex 방식
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.daegu.go.kr"
LIST_URL = f"{BASE_URL}/index.do"
PAGE_SIZE = 10


class DaeguCrawler:
    """대구광역시청 고시공고 크롤러"""

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
        post_data = {
            "menu_id": "00940170",
            "menu_link": "/front/daeguSidoGosi/daeguSidoGosiList.do",
            "pageIndex": str(page),
            "sno": "",
            "gosi_gbn": "",
            "searchBgnDe": "",
            "searchEndDe": "",
            "searchAnnounce_no": "",
            "searchGosi_gbn": "",
            "searchDept_nm": "",
            "postPerPage": "0",
        }
        if keyword:
            post_data["searchTitle"] = keyword

        resp = self.session.post(LIST_URL, data=post_data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: pagination에서 마지막 페이지 번호로 추정
        total_count = 0
        pagination = soup.select_one("div.pagination")
        if pagination:
            # 마지막 페이지 링크에서 총 페이지 수 추출
            last_link = pagination.select("a.page_nextend")
            if last_link:
                onclick = last_link[0].get("onclick", "")
                m = re.search(r'fn_egov_link_page\((\d+)', onclick)
                if m:
                    total_pages = int(m.group(1))
                    total_count = total_pages * PAGE_SIZE

        items = []
        table = soup.select_one("table#bbsList")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            dept = cells[2].get_text(strip=True)
            date = cells[3].get_text(strip=True)

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)

            # href는 javascript:fn_goLinkView('45528', 'A') 형식
            href = link.get("href", "")
            m = re.search(r"fn_goLinkView\('(\d+)',\s*'([^']+)'\)", href)
            if m:
                sno = m.group(1)
                gosi_gbn = m.group(2)
                detail_url = (
                    f"{BASE_URL}/index.do?menu_id=00940170"
                    f"&menu_link=/front/daeguSidoGosi/daeguSidoGosiView.do"
                    f"&sno={sno}&gosi_gbn={gosi_gbn}"
                )
            else:
                detail_url = f"{BASE_URL}/index.do?menu_id=00940170"

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": dept if dept else "대구광역시청",
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
        print(f"[대구광역시청] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = DaeguCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
