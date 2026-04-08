# -*- coding: utf-8 -*-
"""
아산시청 고시공고 크롤러
https://www.asan.go.kr/main/cms/?no=483
eminwon iframe (OfrNotAncmtLSub.jsp -> OfrAction.do), POST, not_ancmt_se_code=01,04,06,07, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


EMINWON_BASE = "https://eminwon.asan.go.kr"
IFRAME_URL = f"{EMINWON_BASE}/emwp/jsp/ofr/OfrNotAncmtLSub.jsp"
ACTION_URL = f"{EMINWON_BASE}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
DETAIL_URL = f"{EMINWON_BASE}/emwp/jsp/ofr/OfrNotAncmtVSub.jsp"
SE_CODE = "01,04,06,07"
PAGE_SIZE = 10
ORGANIZATION_NAME = "아산시청"


class AsanGosiCrawler:
    """아산시청 고시공고 크롤러"""

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
        self._initialized = False

    def _init_session(self):
        """iframe URL 로드하여 세션/쿠키 초기화"""
        if self._initialized:
            return
        try:
            self.session.get(
                IFRAME_URL,
                params={
                    "not_ancmt_se_code": SE_CODE,
                    "list_gubun": "",
                    "ofr_pageSize": str(PAGE_SIZE),
                    "epcCheck": "Y",
                },
                timeout=15
            )
        except Exception:
            pass
        self._initialized = True

    def _fetch_page(self, keyword, page):
        self._init_session()
        data = {
            "pageIndex": str(page),
            "jndinm": "OfrNotAncmtEJB",
            "context": "NTIS",
            "method": "selectListOfrNotAncmt",
            "methodnm": "selectListOfrNotAncmtHomepage",
            "not_ancmt_mgt_no": "",
            "homepage_pbs_yn": "Y",
            "subCheck": "Y",
            "ofr_pageSize": str(PAGE_SIZE),
            "not_ancmt_se_code": SE_CODE,
            "title": "고시공고",
            "countYn": "Y",
            "list_gubun": "",
            "Key": "B_Subject",
            "temp": keyword if keyword else "",
            "not_ancmt_sj": keyword if keyword else "",
            "not_ancmt_cn": "",
            "dept_nm": "",
            "epcCheck": "Y",
        }

        resp = self.session.post(ACTION_URL, data=data, timeout=30)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []

        for tr in soup.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            ths = tr.find_all("th", recursive=False)
            if len(ths) == 1 and len(tds) >= 4:
                number = ths[0].get_text(strip=True)
                if not number.isdigit():
                    continue
                if total_count == 0 and page == 1:
                    total_count = int(number)
                gosi_no = tds[0].get_text(strip=True)
                title_text = tds[1].get_text(strip=True)
                dept = tds[2].get_text(strip=True)
                date = tds[3].get_text(strip=True).replace(".", "-")
                link = tds[1].find("a")
                detail_url = ""
                if link:
                    onclick = link.get("onclick", "") or link.get("href", "")
                    m = re.search(r"searchDetail\(['\"]?(\d+)['\"]?\)", onclick)
                    if m:
                        detail_url = (
                            f"{DETAIL_URL}?not_ancmt_se_code={SE_CODE}"
                            f"&not_ancmt_mgt_no={m.group(1)}"
                        )
                items.append({
                    "number": number,
                    "title": f"[{gosi_no}] {title_text}" if gosi_no else title_text,
                    "date": date,
                    "url": detail_url,
                    "organization": f"{ORGANIZATION_NAME} ({dept})" if dept else ORGANIZATION_NAME,
                })
                continue
            if len(tds) < 6:
                continue
            number = tds[0].get_text(strip=True)
            if not number.isdigit():
                continue
            if total_count == 0 and page == 1:
                total_count = int(number)
            gosi_no = tds[1].get_text(strip=True)
            title_text = tds[2].get_text(strip=True)
            dept = tds[3].get_text(strip=True)
            date = tds[4].get_text(strip=True).replace(".", "-")
            link = tds[2].find("a")
            detail_url = ""
            if link:
                onclick = link.get("onclick", "") or link.get("href", "")
                m = re.search(r"searchDetail\(['\"]?(\d+)['\"]?\)", onclick)
                if m:
                    detail_url = (
                        f"{DETAIL_URL}?not_ancmt_se_code={SE_CODE}"
                        f"&not_ancmt_mgt_no={m.group(1)}"
                    )
            items.append({
                "number": number,
                "title": f"[{gosi_no}] {title_text}" if gosi_no else title_text,
                "date": date,
                "url": detail_url,
                "organization": f"{ORGANIZATION_NAME} ({dept})" if dept else ORGANIZATION_NAME,
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
        print(f"[{ORGANIZATION_NAME} 입찰] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = AsanGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
