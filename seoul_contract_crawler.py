# -*- coding: utf-8 -*-
"""
서울계약마당 입찰공고 크롤러
https://contract.seoul.go.kr/new1/views/pubBidInfo.do
서버 사이드 렌더링, GET 파라미터 기반, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://contract.seoul.go.kr"
LIST_URL = f"{BASE_URL}/new1/views/pubBidInfo.do"
PAGE_SIZE = 100


class SeoulContractCrawler:
    """서울계약마당 입찰공고 크롤러"""

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
        current_year = str(datetime.now().year)
        params = {
            "ps_selectForm": "1",            # 간편검색 모드
            "ps1_fisYear": current_year,     # 기준년도
            "ps1_selectSearch": "1",         # 검색조건: 공고명
            "ps1_searchTxt": keyword if keyword else "",
            "ps_currentPageNo": str(page),
            "ps_recordCountPerPage": str(PAGE_SIZE),
        }

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: "2,234건" 패턴
        total_count = 0
        m = re.search(r'([\d,]+)\s*건', resp.text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        # 목록 파싱: tbody 안의 tr, 매 3행이 1건
        # Row 0 (settxt): 계약종류 + 기관구분 | 발주기관명
        # Row 1 (setst):  제목 (링크 포함)
        # Row 2 (daily):  공고일자, 입찰게시일, 개찰일시
        items = []
        tbody = soup.find("tbody")
        if not tbody:
            return items, total_count

        rows = tbody.find_all("tr")
        i = 0
        while i + 2 < len(rows):
            row_meta = rows[i]       # settxt
            row_title = rows[i + 1]  # setst
            row_date = rows[i + 2]   # daily
            i += 3

            # 메타: 계약종류 + 발주기관
            meta_td = row_meta.find("td", class_="settxt")
            if not meta_td:
                continue
            meta_text = meta_td.get_text(strip=True)
            # 예: "용역자치구  |  금천구" or "용역투자출연기관  |  서울교통공사"
            org = "서울계약마당"
            if "|" in meta_text:
                parts = meta_text.split("|")
                if len(parts) >= 2:
                    org = parts[-1].strip()

            # 제목 + 상세 링크
            title_td = row_title.find("td", class_="setst")
            if not title_td:
                continue
            link = title_td.find("a")
            title = link.get_text(strip=True) if link else title_td.get_text(strip=True)

            # 상세 URL: bidPopup_getBidInfoDtlUrl('5', 'R26BK01391735', '000', '2')
            detail_url = LIST_URL
            bid_no = ""
            if link:
                onclick = link.get("onclick", "")
                m = re.search(
                    r"bidPopup_getBidInfoDtlUrl\(\s*'(\d+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'(\d+)'\s*\)",
                    onclick,
                )
                if m:
                    sys_gb = m.group(1)
                    bid_id = m.group(2)
                    bid_seq = m.group(3)
                    bid_type = m.group(4)
                    bid_no = bid_id
                    detail_url = (
                        f"{BASE_URL}/new1/views/pubBidInfoDtl.do"
                        f"?bidNo={bid_id}&bidSeq={bid_seq}"
                    )

            # 날짜: 공고일자
            date = ""
            date_tds = row_date.find_all("td")
            for td in date_tds:
                text = td.get_text(strip=True)
                m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
                if m:
                    date = m.group(1)
                    break

            items.append({
                "number": bid_no,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": org if org else "서울계약마당",
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
        print(f"[서울계약마당] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = SeoulContractCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공사' 검색 ===")
    results2 = crawler.search("공사", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
