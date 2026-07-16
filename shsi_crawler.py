# -*- coding: utf-8 -*-
"""
시흥도시공사 (shsi) - xlsx 49행
통합검색(selectSearchTotalList.do) 단일 엔드포인트 방식.

xlsx 통합검색 URL: https://www.shsi.or.kr/PageLink.do
실제 검색 API:   /main/cop/bbs/selectSearchTotalList.do
빈 검색어(searchKeyword='') + category='1'(게시판 카테고리) + recordCountPerPage=대용량
→ 한 번의 POST로 게시판 전체 통합 결과를 가져온다.
"""
import re
import time
import html
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


class SHSICrawler:
    """시흥도시공사 통합검색 크롤러."""

    BASE_URL = "https://www.shsi.or.kr"
    SEARCH_PATH = "/main/cop/bbs/selectSearchTotalList.do"

    # category='1' = 게시판. 웹페이지(카테고리 없음/2)는 공고성 자료가 아니어서 제외.
    CATEGORY = "1"
    RECORD_COUNT_PER_PAGE = 1000  # 한 번에 최대치 반환

    MAX_RETRIES = 5
    RETRY_DELAY = 1.5

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://www.shsi.or.kr/PageLink.do",
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.verify = False

    def _fetch(self, page_index=1):
        url = self.BASE_URL + self.SEARCH_PATH
        data = {
            "category": self.CATEGORY,
            "pageIndex": str(page_index),
            "searchKeyword": "",
            "recordCountPerPage": str(self.RECORD_COUNT_PER_PAGE),
        }
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.post(url, data=data, timeout=60)
                r.raise_for_status()
                r.encoding = "utf-8"
                return BeautifulSoup(r.text, "lxml"), r.text
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
        return None, ""

    def _get_total(self, page_html):
        m = re.search(r"총\s*<[^>]*>\s*([\d,]+)", page_html)
        return int(m.group(1).replace(",", "")) if m else 0

    @staticmethod
    def _clean(text):
        text = html.unescape(text or "")
        text = text.replace("\xa0", " ")
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _parse_onclick(onclick):
        """
        onclick=goBbsDetail('bbsId','nttId','uuid','010000','010100','010400','main')
        -> (bbsId, nttId, uuid, menuNo, subMenuNo, thirdMenuNo, branchId)
        """
        args = re.findall(r"'([^']*)'", onclick or "")
        return args if len(args) >= 7 else None

    def _detail_url(self, bbs_id, ntt_id, uuid, menu_no, sub_menu, third_menu, branch_id):
        # goBbsDetail JS를 그대로 URL로 재현:
        # /{branchId}/PageLink.do?link=forward:/cop/bbs/selectBoardArticle.do?bbsId=...&nttId=...&uuid=...
        # menuNo/subMenuNo/thirdMenuNo도 함께 전달해야 정상 렌더링.
        return (
            f"{self.BASE_URL}/{branch_id}/PageLink.do"
            f"?link=forward%3A%2Fcop%2Fbbs%2FselectBoardArticle.do"
            f"%3FbbsId%3D{bbs_id}%26nttId%3D{ntt_id}%26uuid%3D{uuid}"
            f"&menuNo={menu_no}&subMenuNo={sub_menu}&thirdMenuNo={third_menu}"
        )

    def _parse_items(self, soup):
        results = []
        if not soup:
            return results
        for li in soup.select("ul.search_view > li"):
            h4 = li.find("h4")
            if not h4:
                continue
            a = h4.find("a")
            if not a:
                continue
            onclick = a.get("onclick", "") or ""
            args = self._parse_onclick(onclick)
            # 게시판 항목(goBbsDetail)만 채택. 웹페이지(goContentDetail) 등은 건너뜀.
            if not args:
                continue
            bbs_id, ntt_id, uuid, menu_no, sub_menu, third_menu, branch_id = args[:7]

            title = self._clean(a.get_text(" "))
            if not title or len(title) < 2:
                continue

            date_span = li.find("span")
            date_raw = self._clean(date_span.get_text(" ")) if date_span else ""
            m = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", date_raw)
            date = (
                f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
                if m else ""
            )

            src_tag = li.find(class_="search_loc")
            src_text = self._clean(src_tag.get_text(" ")) if src_tag else ""
            # "출처사이트 : 보도자료" -> "보도자료"
            source = re.sub(r"^출처사이트\s*:\s*", "", src_text).strip()

            url = self._detail_url(bbs_id, ntt_id, uuid, menu_no, sub_menu, third_menu, branch_id)

            results.append({
                "title": title,
                "date": date,
                "url": url,
                "organization": source or "통합검색",
                "number": ntt_id,
            })
        return results

    def search(self, keyword="", max_pages=999, start_date=None, end_date=None):
        soup, page_html = self._fetch(page_index=1)
        if soup is None:
            print("[시흥도시공사] 검색 페이지 로드 실패", flush=True)
            return []

        total = self._get_total(page_html)
        items = self._parse_items(soup)

        # recordCountPerPage=1000 로도 안 잡히면 후속 페이지 순회 (안전장치)
        if total and len(items) < total and len(items) >= self.RECORD_COUNT_PER_PAGE:
            page = 2
            while len(items) < total and page <= max_pages:
                time.sleep(0.3)
                soup2, _ = self._fetch(page_index=page)
                page_items = self._parse_items(soup2) if soup2 else []
                if not page_items:
                    break
                items.extend(page_items)
                page += 1

        # dedup by url
        seen = set()
        unique = []
        for it in items:
            key = it["url"] or (it["title"], it["date"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(it)

        # 날짜 필터
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        filtered = [
            it for it in unique
            if not it["date"] or (start_date <= it["date"][:10] <= end_date)
        ]
        filtered.sort(key=lambda x: x["date"] or "", reverse=True)

        print(f"[시흥도시공사] 총 {total}건 표기 / 파싱 {len(unique)}건 / 필터 후 {len(filtered)}건", flush=True)
        return filtered


def main():
    import urllib3
    urllib3.disable_warnings()
    c = SHSICrawler()
    t0 = time.time()
    items = c.search(start_date="2000-01-01", end_date="2099-12-31")
    print(f"{len(items)}건 / {time.time()-t0:.0f}초")
    from collections import Counter
    for k, v in Counter(it["organization"] for it in items).most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
