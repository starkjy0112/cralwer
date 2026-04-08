# -*- coding: utf-8 -*-
"""
화천군청 입찰공고 크롤러
http://www.ihc.go.kr/www/contents.do?key=115
e-minwon iframe 기반, POST to OfrAction.do, not_ancmt_se_code=02
"""
import math
import re
from datetime import datetime, timedelta
import time
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "http://eminwon.ihc.go.kr"
JSP_URL = f"{BASE_URL}/emwp/jsp/ofr/OfrNotAncmtL.jsp"
ACTION_URL = f"{BASE_URL}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "화천군청"
SE_CODE = "02"


class HwacheonBidCrawler:
    """화천군청 입찰공고 크롤러"""

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
        try:
            self.session.get(
                f"{JSP_URL}?not_ancmt_se_code={SE_CODE}&homepage_pbs_yn=Y&subCheck=N",
                timeout=30)
        except Exception:
            pass

    def _fetch_page(self, keyword, page):
        data = {
            "pageIndex": str(page),
            "jndinm": "OfrNotAncmtEJB",
            "context": "NTIS",
            "method": "selectListOfrNotAncmt",
            "methodnm": "selectListOfrNotAncmtHomepage",
            "not_ancmt_se_code": SE_CODE,
            "homepage_pbs_yn": "Y",
            "subCheck": "N",
            "ofr_pageSize": str(PAGE_SIZE),
            "countYn": "Y",
            "not_ancmt_sj": "",
            "not_ancmt_cn": "",
            "dept_nm": "",
            "not_ancmt_reg_no": "",
            "recent_mm": "",
            "yyyy": "",
            "yyyymmdd": "",
        }
        if keyword:
            data["not_ancmt_sj"] = keyword

        resp = None
        last_err = None
        for attempt in range(3):
            try:
                resp = self.session.post(ACTION_URL, data=data, timeout=30)
                break
            except Exception as e:
                last_err = e
                time.sleep(1 * (attempt + 1))
        if resp is None:
            return [], 0
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        text = soup.get_text()
        m = re.search(r'전체게시물\s*:\s*(\d[\d,]*)\s*개', text)
        if not m:
            m = re.search(r'(\d[\d,]*)\s*개', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            # 화천 eminwon: 7 컬럼 (번호, 고시번호, 제목, 부서, 등록일, 기간, 조회수)
            if len(cells) < 5:
                continue
            # onclick은 td 또는 td 안의 a 태그에 있음
            onclick = ""
            for c in cells:
                oc = c.get("onclick", "")
                if "searchDetail" in oc:
                    onclick = oc
                    break
                link = c.find("a")
                if link:
                    oc = link.get("onclick", "")
                    if "searchDetail" in oc:
                        onclick = oc
                        break
            if not onclick:
                continue

            first_text = cells[0].get_text(strip=True)
            if not first_text.isdigit():
                continue

            number = first_text
            notice_no = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            title = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            dept = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            date = cells[4].get_text(strip=True) if len(cells) > 4 else ""

            items.append({
                "number": notice_no if notice_no else number,
                "title": title,
                "date": date,
                "url": "http://www.ihc.go.kr/www/contents.do?key=115",
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
        print(f"[{ORGANIZATION_NAME} 입찰공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = HwacheonBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
