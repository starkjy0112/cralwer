# -*- coding: utf-8 -*-
"""
광주도시관리공사 통합검색 크롤러
https://www.gumc.or.kr/information/search
"""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gumc.or.kr"
SEARCH_URL = f"{BASE_URL}/information/search"


class GUMCCrawler:
    """광주도시관리공사 통합검색 크롤러"""

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

    def _fetch_search(self, keyword):
        """통합검색 결과를 가져옵니다."""
        resp = self.session.post(
            SEARCH_URL,
            data={"q": keyword},
            timeout=30,
        )
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        items = []
        result_links = soup.select(".result-list ul li a")
        for a in result_links:
            href = a.get("href", "")
            text = a.get_text(strip=True)

            # "카테고리 > 제목" 형식에서 분리
            organization = ""
            title = text
            if " > " in text:
                parts = text.split(" > ", 1)
                organization = parts[0].strip()
                title = parts[1].strip()

            url = urljoin(BASE_URL, href) if href else ""

            items.append({
                "number": "",
                "title": title,
                "date": "",
                "url": url,
                "organization": organization,
            })

        return items

    WORKERS = 10

    def _fetch_date(self, url):
        """상세 페이지에서 날짜 추출"""
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            text = resp.text
            m = re.search(r'(\d{4}[./-]\d{2}[./-]\d{2})', text)
            if m:
                return m.group(1).replace(".", "-").replace("/", "-")
        except Exception:
            pass
        return ""

    def _fetch_dates_parallel(self, results):
        """상세 페이지에서 날짜를 병렬로 가져오기"""
        urls = [(i, r["url"]) for i, r in enumerate(results) if r["url"]]
        if not urls:
            return

        with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
            futures = {
                executor.submit(self._fetch_date, url): idx
                for idx, url in urls
            }
            done = 0
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    date = future.result()
                    if date:
                        results[idx]["date"] = date
                except Exception:
                    pass
                done += 1
                if done % 50 == 0:
                    print(f"  날짜 조회 진행: {done}/{len(urls)}")

    def search(self, keyword="", max_pages=10):
        """게시물을 검색합니다."""
        if not keyword:
            keyword = " "

        all_items = self._fetch_search(keyword)
        max_items = max_pages * 10
        limited = all_items[:max_items]

        print(f"  검색 결과: {len(all_items)}건, 반환: {len(limited)}건")

        if limited:
            print(f"  날짜 조회 시작 ({len(limited)}건)...")
            self._fetch_dates_parallel(limited)

        limited.sort(key=lambda x: x["date"], reverse=True)
        print(f"[광주도시관리공사] 완료: 총 {len(limited)}건")
        return limited


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")

    crawler = GUMCCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
