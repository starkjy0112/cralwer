# -*- coding: utf-8 -*-
"""
통영관광개발공사 입찰정보 크롤러
http://corp.ttdc.kr/board/board.aspx?tbl=bidding

ASP.NET WebForms 기반 (VIEWSTATE + __doPostBack 방식).
검색: POST로 ddlSearchCondition + txtSearchWord 전송.
페이지 이동: __doPostBack('dataPager$ctl01$ctlXX', '') 방식.
"""
import re
import requests
from bs4 import BeautifulSoup


BASE_URL = "http://corp.ttdc.kr"
BOARD_URL = f"{BASE_URL}/board/board.aspx?tbl=bidding"


class TTDCCrawler:
    """통영관광개발공사 입찰정보 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    def _extract_asp_fields(self, soup):
        """VIEWSTATE 등 ASP.NET hidden 필드 추출"""
        fields = {}
        for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR",
                      "__VIEWSTATEENCRYPTED", "__EVENTVALIDATION"):
            tag = soup.find("input", id=name)
            fields[name] = tag["value"] if tag else ""
        return fields

    def _parse_page(self, soup):
        """테이블에서 게시글 파싱"""
        items = []
        table = soup.select_one("table")
        if not table:
            return items

        for row in table.select("tr")[1:]:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            link = cells[1].select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            detail_url = f"{BASE_URL}{href}" if href.startswith("/") else href
            author = cells[2].get_text(strip=True)
            date = cells[3].get_text(strip=True)

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": author,
            })

        return items

    def _get_total_pages(self, soup):
        """Page : 1 / 17 에서 총 페이지 수 추출"""
        m = re.search(r"Page\s*:\s*\d+\s*/\s*(\d+)", soup.get_text(), re.DOTALL)
        return int(m.group(1)) if m else 1

    def _get_pager_targets(self, soup):
        """페이지네이션 __doPostBack 타겟 목록 추출"""
        targets = {}
        for a in soup.find_all("a", href=re.compile(r"__doPostBack")):
            m = re.search(r"__doPostBack\('([^']+)'", a.get("href", ""))
            text = a.get_text(strip=True)
            if m and text.isdigit():
                targets[int(text)] = m.group(1)
        return targets

    def search(self, keyword="", max_pages=1000):
        """입찰정보를 검색합니다."""
        # 1단계: 초기 페이지 GET
        resp = self.session.get(BOARD_URL, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        asp_fields = self._extract_asp_fields(soup)

        # 2단계: 검색 POST (키워드가 있으면)
        if keyword:
            data = dict(asp_fields)
            data["ctl00$MainContent$ctl00$ddlSearchCondition"] = "Title"
            data["ctl00$MainContent$ctl00$txtSearchWord"] = keyword
            data["ctl00$MainContent$ctl00$btnSearch"] = "검색"
            resp = self.session.post(BOARD_URL, data=data, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            asp_fields = self._extract_asp_fields(soup)

        # 첫 페이지 파싱
        total_pages = min(self._get_total_pages(soup), max_pages)
        all_items = self._parse_page(soup)
        print(f"  [Page 1/{total_pages}] {len(all_items)}건 수집")

        if total_pages <= 1:
            print(f"[통영관광개발공사] 완료: 총 {len(all_items)}건")
            return all_items

        # 3단계: 나머지 페이지 순차 조회 (ASP.NET은 VIEWSTATE가 순차 의존)
        for page in range(2, total_pages + 1):
            pager_targets = self._get_pager_targets(soup)

            if page in pager_targets:
                target = pager_targets[page]
            else:
                # "Next" 또는 "..." 링크 찾기
                next_link = None
                for a in soup.find_all("a", href=re.compile(r"__doPostBack")):
                    text = a.get_text(strip=True)
                    if text in ("Next", "..."):
                        m = re.search(r"__doPostBack\('([^']+)'", a.get("href", ""))
                        if m:
                            next_link = m.group(1)
                            break
                if not next_link:
                    break
                target = next_link

            data = dict(asp_fields)
            data["__EVENTTARGET"] = target
            data["__EVENTARGUMENT"] = ""
            if keyword:
                data["ctl00$MainContent$ctl00$ddlSearchCondition"] = "Title"
                data["ctl00$MainContent$ctl00$txtSearchWord"] = keyword

            try:
                resp = self.session.post(BOARD_URL, data=data, timeout=15)
                resp.encoding = "utf-8"
                soup = BeautifulSoup(resp.text, "html.parser")
                asp_fields = self._extract_asp_fields(soup)

                items = self._parse_page(soup)
                if not items:
                    break
                all_items.extend(items)
            except Exception as e:
                print(f"  [Page {page}] Error: {e}")
                break

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[통영관광개발공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = TTDCCrawler()
    print("=== 전체 조회 ===")
    results = crawler.search("", max_pages=1000)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print(f"\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=1000)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
