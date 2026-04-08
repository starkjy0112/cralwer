# -*- coding: utf-8 -*-
"""
울진군청 고시/공고 크롤러
https://www.uljin.go.kr/index.uljin?menuCd=DOM_000000103002007000
POST 기반, bbs_list (ul/li), 10건/페이지, startPage/goPage
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.uljin.go.kr"
LIST_URL = f"{BASE_URL}/index.uljin"
MENU_CD = "DOM_000000103002007000"
PAGE_SIZE = 10
ORGANIZATION_NAME = "울진군청"


class UljinCrawler:
    """울진군청 고시/공고 크롤러"""

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
            "menuCd": MENU_CD,
            "startPage": str(page),
        }
        if keyword:
            params["searchType"] = "NOT_ANCMT_SJ"
            params["searchTerm"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []

        # Pagination: goPage('N')
        max_page = 1
        for m_p in re.finditer(r"goPage\(\s*'(\d+)'\s*\)", resp.text):
            p_num = int(m_p.group(1))
            if p_num > max_page:
                max_page = p_num
        if max_page > 1:
            total_count = max_page * PAGE_SIZE

        bbs_list = soup.select_one("ul.bbs_list")
        if not bbs_list:
            return items, total_count

        for li in bbs_list.find_all("li"):
            link = li.find("a")
            if not link:
                continue

            strong = link.find("strong")
            title = strong.get_text(strip=True) if strong else link.get_text(strip=True)

            href = link.get("href", "")
            if href and href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            elif href and href.startswith("http"):
                detail_url = href
            else:
                detail_url = ""

            # Parse info: 공고번호 : xxx | 부서 : xxx | 게재일 : 2026-04-03
            em = link.find("em", class_="info")
            number = ""
            date = ""
            if em:
                info_text = em.get_text()
                m_no = re.search(r'공고번호\s*:\s*(.+?)(?:\s*\||\s*$)', info_text)
                if m_no:
                    number = m_no.group(1).strip()
                m_date = re.search(r'게재일\s*:\s*(\d{4}-\d{2}-\d{2})', info_text)
                if m_date:
                    date = m_date.group(1)

            if not total_count and number:
                pass  # Can't derive total from number in this format

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
        print(f"[{ORGANIZATION_NAME} 고시/공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = UljinCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
