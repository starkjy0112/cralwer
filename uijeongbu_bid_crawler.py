# -*- coding: utf-8 -*-
"""
의정부시청 입찰정보 크롤러
https://www.ui4u.go.kr/portal/saeol/gosiList.do?seCode=02&mId=0301090000
GET 기반, 10건/페이지
컬럼: 번호, 고시공고번호, 제목, 담당부서, 등록일
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.ui4u.go.kr"
LIST_URL = f"{BASE_URL}/portal/saeol/gosiList.do"
PAGE_SIZE = 100


class UijeongbuBidCrawler:
    """의정부시청 입찰정보 크롤러"""

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
            "seCode": "02",
            "mId": "0301090000",
            "pageIndex": page,
        }
        if keyword:
            params["searchType"] = "NOT_ANCMT_SJ"
            params["searchTxt"] = keyword

        resp = self.session.post(LIST_URL, data=params, timeout=15)
        resp.encoding = "utf-8"
        html = resp.text
        soup = BeautifulSoup(html, "lxml")

        # 총 건수: goPage() 호출에서 최대 페이지 번호 추출
        total_count = 0
        pages = re.findall(r'goPage\((\d+)\)', html)
        if pages:
            max_page = max(int(p) for p in pages)
            total_count = max_page * PAGE_SIZE

        items = []
        table = soup.select_one("table.bod_list") or soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        if not rows:
            rows = table.select("tr")[1:]

        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[2]
            dept = cells[3].get_text(strip=True)
            date = cells[4].get_text(strip=True)

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            title = re.sub(r'새글$', '', title).strip()

            onclick = link.get("onclick", "")
            m_view = re.search(r"boardView\('(\d+)',\s*'(\d+)'\)", onclick)
            if m_view:
                detail_url = f"{BASE_URL}/portal/saeol/gosiView.do?seCode=02&mId=0301090000&gosiGbn={m_view.group(1)}&gosiSeq={m_view.group(2)}"
            else:
                detail_url = f"{LIST_URL}?seCode=02&mId=0301090000"

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "의정부시청",
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
        print(f"[의정부시청 입찰정보] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = UijeongbuBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
