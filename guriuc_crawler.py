# -*- coding: utf-8 -*-
"""
구리도시공사 입찰정보 크롤러
https://www.guriuc.or.kr/bbsArticle/list.do?bbsId=BID_INFO
POST 기반, jsessionid 필요
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.guriuc.or.kr"
LIST_URL = f"{BASE_URL}/bbsArticle/list.do"


class GURIUCCrawler:
    """구리도시공사 입찰정보 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        self.session.verify = False
        self._post_url = LIST_URL

    def _init_session(self):
        """GET으로 세션 초기화, jsessionid 추출"""
        resp = self.session.get(LIST_URL, params={"bbsId": "BID_INFO"}, timeout=30)
        resp.encoding = "utf-8"
        m = re.search(r'jsessionid=([A-Z0-9.]+)', resp.text)
        if m:
            self._post_url = f"{LIST_URL};jsessionid={m.group(1)}"

    def _fetch_page(self, keyword, page):
        """게시판 목록 한 페이지를 가져옵니다."""
        resp = self.session.post(
            self._post_url,
            data={
                "pageIndex": str(page),
                "bbsId": "BID_INFO",
                "searchType": "all",
                "searchValue": keyword,
            },
            timeout=15,
        )
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 총 건수 파싱: <p class="total">전체 <span class="em on">161</span>건</p>
        total_count = 0
        span = soup.select_one("p.total span.em")
        if span:
            try:
                total_count = int(span.get_text(strip=True).replace(",", ""))
            except ValueError:
                pass

        # 게시글 파싱
        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tr")[1:]  # 헤더 제외
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            author = cells[3].get_text(strip=True)
            date = cells[4].get_text(strip=True)

            link = title_cell.select_one("a")
            detail_url = ""
            title = ""
            if link:
                title = link.get_text(strip=True)
                onclick = link.get("onclick", "")
                seq_m = re.search(r'fn_view\((\d+)\)', onclick)
                if seq_m:
                    seq = seq_m.group(1)
                    detail_url = f"{BASE_URL}/bbsArticle/view.do?bbsId=BID_INFO&seq={seq}"

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": author,
            })

        return items, total_count

    WORKERS = 5

    def search(self, keyword="", max_pages=10):
        """입찰정보를 검색합니다."""
        self._init_session()

        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / 10))
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
        print(f"[구리도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")

    crawler = GURIUCCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
