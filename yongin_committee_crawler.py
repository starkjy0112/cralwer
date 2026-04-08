# -*- coding: utf-8 -*-
"""
용인특례시청 공법선정위원회 크롤러
http://www.yongin.go.kr/user/bbs/BD_selectBbsList.do?q_bbsCode=1156
GET 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "http://www.yongin.go.kr"
LIST_URL = f"{BASE_URL}/user/bbs/BD_selectBbsList.do"
PAGE_SIZE = 100


class YonginCommitteeCrawler:
    """용인특례시청 공법선정위원회 크롤러"""

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
        self.session.verify = False

    def _fetch_page(self, keyword, page):
        params = {
            "q_bbsCode": "1156",
            "q_currPage": str(page),
            "q_rowPerPage": str(PAGE_SIZE),
        }
        if keyword:
            params["q_searchKeyType"] = "sj___1156"
            params["q_searchVal"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 전체 133건 (1 / 14 Page)
        total_count = 0
        result_wrap = soup.find(class_="result_wrap")
        if result_wrap:
            m = re.search(r'전체\s*([\d,]+)\s*건', result_wrap.get_text())
            if m:
                total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 4:
                continue

            # Check if notice
            notice_td = row.select_one("td.notice")
            number = tds[0].get_text(strip=True)
            if notice_td:
                number = "공지"

            title_td = row.select_one("td.td_al")
            if not title_td:
                title_td = tds[1]

            link = title_td.find("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            # onclick="opView('20260212163447263');return false;"
            onclick = link.get("onclick", "")
            m_view = re.search(r"opView\('([^']+)'\)", onclick)
            if m_view:
                sn = m_view.group(1)
                detail_url = f"{BASE_URL}/user/bbs/BD_selectBbs.do?q_bbsCode=1156&q_bbscttSn={sn}"
            elif href and not href.startswith("#"):
                if href.startswith("/"):
                    detail_url = f"{BASE_URL}{href}"
                else:
                    detail_url = f"{BASE_URL}/user/bbs/{href}"
            else:
                detail_url = ""

            date = tds[3].get_text(strip=True) if len(tds) > 3 else ""

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "용인특례시청",
            })

        return items, total_count

    WORKERS = 50

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
        print(f"[용인특례시청 공법선정위원회] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    crawler = YonginCommitteeCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
