# -*- coding: utf-8 -*-
"""
송파구청 입찰공고 크롤러
http://bid.songpa.go.kr/ejudata/ConstructionBidInfo.do?menuId=bid&subMenuId=bidInfo&thirdMenuId=I_A
POST 기반, li.bid_item 카드 리스트, pageIndex 방식
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "http://bid.songpa.go.kr"
LIST_URL = f"{BASE_URL}/ejudata/ConstructionBidInfo.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "송파구청"


class SongpaBidCrawler:
    """송파구청 입찰공고 크롤러"""

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
        data = {
            "pageIndex": str(page),
            "taskClCd": "3",
            "EP_COJ_GG": "tbid/tbidList.do",
            "E_OPEN_DT_S": "",
            "E_OPEN_DT_E": "",
            "e_BID_NAME": keyword if keyword else "",
        }

        resp = self.session.post(LIST_URL, data=data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        text = soup.get_text()
        m = re.search(r'총\s*(\d[\d,]*)\s*건', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))
        if not total_count:
            m2 = re.search(r'전체\s*(\d[\d,]*)', text)
            if m2:
                total_count = int(m2.group(1).replace(",", ""))

        items = []
        # Parse li.bid_item cards
        bid_items = soup.select("li.bid_item")
        for idx, item in enumerate(bid_items):
            a_tag = item.select_one("a.bid_link")
            if not a_tag:
                continue

            title_el = a_tag.select_one("h4.bid_subject")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            href = a_tag.get("href", "")
            detail_url = href if href and href.startswith("http") else LIST_URL

            # Badge (category)
            badge = a_tag.select_one("span.bid_badge")
            category = badge.get_text(strip=True) if badge else ""

            # Organization
            org_el = a_tag.select_one("span.bid_order")
            org = org_el.get_text(strip=True) if org_el else ORGANIZATION_NAME

            # Dates from summary
            date_str = ""
            summary_items = a_tag.select("ul.summary li")
            for li in summary_items:
                spans = li.select("span")
                if len(spans) >= 2:
                    label = spans[0].get_text(strip=True)
                    value = spans[1].get_text(strip=True)
                    if "공고일자" in label or "공고일" in label:
                        dm = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', value)
                        if dm:
                            date_str = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
                        break

            if not date_str:
                # Fallback: first date found
                for li in summary_items:
                    txt = li.get_text(strip=True)
                    dm = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', txt)
                    if dm:
                        date_str = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
                        break

            if category:
                title = f"[{category}] {title}"

            items.append({
                "number": str(idx + 1 + (page - 1) * PAGE_SIZE),
                "title": title,
                "date": date_str,
                "url": detail_url,
                "organization": org if org else ORGANIZATION_NAME,
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
        print(f"[{ORGANIZATION_NAME} 입찰공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = SongpaBidCrawler()
    print("=== 전체 조회 ===")
    results = crawler.search("", max_pages=1)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
