# -*- coding: utf-8 -*-
"""
수원특례시청 공고/고시/입법예고 크롤러
https://www.suwon.go.kr/web/saeallOfr/BD_ofrList.do
POST 기반, 10건/페이지 (OpenWorks 프레임워크)
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.suwon.go.kr"
LIST_URL = f"{BASE_URL}/web/saeallOfr/BD_ofrList.do"
PAGE_SIZE = 100
ORGANIZATION_NAME = "수원특례시청"


class SuwonCrawler:
    """수원특례시청 공고/고시/입법예고 크롤러"""

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
            "q_currPage": str(page),
            "q_rowPerPage": str(PAGE_SIZE),
        }
        if keyword:
            data["q_searchKeyTy"] = "SJ"
            data["q_searchVal"] = keyword

        resp = self.session.post(LIST_URL, data=data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # Parse total count - "총 게시물 : <span>N</span>개" or "총 N건"
        total_count = 0
        total_msg = soup.find("div", class_="total_msg") or soup.find("p", class_="total")
        if total_msg:
            span = total_msg.find("span") or total_msg.find("strong")
            if span:
                try:
                    total_count = int(re.sub(r"[^\d]", "", span.get_text(strip=True)))
                except ValueError:
                    pass
        if not total_count:
            text = soup.get_text()
            m = re.search(r'총\s*([\d,]+)\s*건', text)
            if m:
                total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.find("table", class_="table_style2") or soup.find("table", class_="bbsList")
        if not table:
            # Find the main board table
            for t in soup.find_all("table"):
                caption = t.find("caption")
                if caption and ("공고" in caption.text or "고시" in caption.text or "목록" in caption.text):
                    table = t
                    break
        if not table:
            for t in soup.find_all("table"):
                rows = t.find_all("tr")
                if 5 < len(rows) < 25:
                    table = t
                    break

        if table:
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 4:
                    continue
                number = tds[0].get_text(strip=True)

                # Find title and link
                title = ""
                detail_url = ""
                for td in tds:
                    a_tag = td.find("a")
                    if a_tag:
                        title = a_tag.get_text(strip=True)
                        href = a_tag.get("href", "")
                        onclick = a_tag.get("onclick", "")
                        if onclick:
                            m_id = re.search(r"opDetail\('([^']+)'\)", onclick)
                            if m_id:
                                detail_url = f"{BASE_URL}/web/saeallOfr/BD_ofrView.do?q_ofrMgtno={m_id.group(1)}"
                        if not detail_url and href and href != "#" and not href.startswith("javascript"):
                            if href.startswith("BD_ofrView"):
                                detail_url = f"{BASE_URL}/web/saeallOfr/{href}"
                            elif href.startswith("/"):
                                detail_url = f"{BASE_URL}{href}"
                            else:
                                detail_url = href
                        break

                if not title:
                    continue

                # Find date
                date = ""
                for td in tds:
                    td_text = td.get_text(strip=True)
                    if re.match(r'\d{4}[-./]\d{2}[-./]\d{2}', td_text):
                        date = td_text[:10].replace(".", "-")
                        break

                items.append({
                    "number": number,
                    "title": title,
                    "date": date,
                    "url": detail_url,
                    "organization": ORGANIZATION_NAME,
                })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = SuwonCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
