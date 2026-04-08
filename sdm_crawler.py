# -*- coding: utf-8 -*-
"""
서대문구청 공지사항 크롤러
https://www.sdm.go.kr/news/notice/notice.do
POST 기반, euc-kr 인코딩, 10건/페이지
form: frm, sdmBoardConfSeq=82
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.sdm.go.kr"
LIST_URL = f"{BASE_URL}/news/notice/notice.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "서대문구청"


class SdmCrawler:
    """서대문구청 공지사항 크롤러"""

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
        data = {
            "sdmBoardConfSeq": "82",
            "mode": "list",
            "cp": str(page),
        }
        resp = self.session.post(LIST_URL, data=data, timeout=15)
        # Server may respond with euc-kr
        if "euc-kr" in resp.headers.get("Content-Type", "").lower():
            resp.encoding = "euc-kr"
        else:
            resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        # totA hidden input
        tot_input = soup.find("input", {"name": "totA"})
        if tot_input and tot_input.get("value"):
            try:
                total_count = int(tot_input["value"])
            except ValueError:
                pass
        if not total_count:
            text = soup.get_text()
            m = re.search(r'총\s*(\d[\d,]*)', text)
            if m:
                total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table.boardList")
        if not table:
            for t in soup.find_all("table"):
                if t.select("td.aleft"):
                    table = t
                    break
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            a_tag = title_cell.select_one("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            onclick = a_tag.get("href", "") or a_tag.get("onclick", "")
            seq_m = re.search(r"goView\('(\d+)'\)", onclick)
            if seq_m:
                detail_url = f"{LIST_URL}?mode=view&sdmBoardSeq={seq_m.group(1)}&sdmBoardConfSeq=82"
            else:
                detail_url = LIST_URL

            dept = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            date_str = cells[3].get_text(strip=True) if len(cells) > 3 else ""

            m = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', date_str)
            if m:
                date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

            items.append({
                "number": number,
                "title": title,
                "date": date_str,
                "url": detail_url,
                "organization": dept if dept else ORGANIZATION_NAME,
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE)) if total_count else max_pages
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

        if keyword:
            all_items = [item for item in all_items if keyword in item["title"]]
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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = SdmCrawler()
    print("=== 전체 조회 ===")
    results = crawler.search("", max_pages=1)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
