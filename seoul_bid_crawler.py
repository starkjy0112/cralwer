# -*- coding: utf-8 -*-
"""
서울특별시청 입찰공고 크롤러
https://www.seoul.go.kr/news/news_tender.do
seoulboard.seoul.go.kr 기반, bbsNo=163, HTML 파싱, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.seoul.go.kr"
LIST_URL = f"{BASE_URL}/news/news_tender.do"
PAGE_SIZE = 100


class SeoulBidCrawler:
    """서울특별시청 입찰공고 크롤러"""

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
            "bbsNo": "163",
            "curPage": str(page),
            "cntPerPage": str(PAGE_SIZE),
        }
        if keyword:
            params["srchKey"] = "sj"      # sj = 제목 검색
            params["srchText"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: "총 <strong>12459</strong>건" 텍스트에서 추출
        total_count = 0
        point_el = soup.select_one("div.sib-lst-top-left span strong.sib-point-color")
        if point_el:
            try:
                total_count = int(point_el.get_text(strip=True))
            except ValueError:
                pass
        if total_count == 0:
            # 폴백: 마지막 페이지 링크에서 추출
            last_link = soup.find("a", class_="sib-paging-last")
            if last_link:
                href = last_link.get("href", "")
                m = re.search(r'curPage=(\d+)', href)
                if m:
                    total_count = int(m.group(1)) * PAGE_SIZE

        # 목록 파싱: <tr> 안에 sib-lst-type-basic-subject 클래스의 <td>
        items = []
        rows = soup.select("table tr")
        for row in rows:
            subject_td = row.select_one("td.sib-lst-type-basic-subject")
            if not subject_td:
                continue

            # 제목 + 상세 URL
            link = subject_td.find("a")
            if not link:
                continue
            title = link.get_text(strip=True)

            # nttNo 추출: fnTbbsView('454045')
            onclick = link.get("href", "")
            ntt_no = ""
            m = re.search(r"fnTbbsView\('(\d+)'\)", onclick)
            if m:
                ntt_no = m.group(1)
            detail_url = f"{LIST_URL}?bbsNo=163&nttNo={ntt_no}" if ntt_no else LIST_URL

            # 담당부서: 5개 TD 중 td[2]가 담당부서 (td[0]=번호, td[1]=제목, td[2]=부서, td[3]=날짜, td[4]=조회수)
            tds = row.find_all("td")
            dept = ""
            hidden_tds = row.select("td.sib-lst-type-basic-tablet-hidden")
            if len(hidden_tds) >= 2:
                dept = hidden_tds[1].get_text(strip=True)  # 두 번째가 담당부서

            # 번호: 첫 번째 hidden td
            number = ""
            if hidden_tds:
                number = hidden_tds[0].get_text(strip=True)

            # 등록일
            date = ""
            for td in tds:
                text = td.get_text(strip=True)
                if re.match(r"\d{4}-\d{2}-\d{2}", text):
                    date = text
                    break

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": dept if dept else "서울특별시청",
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10):
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

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[서울특별시청] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = SeoulBidCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
