# -*- coding: utf-8 -*-
"""
제주특별자치도개발공사 통합검색 크롤러
https://www.jpdc.co.kr/help/search.htm
"""
import re
import requests
from bs4 import BeautifulSoup, NavigableString


BASE_URL = "https://www.jpdc.co.kr"


class JPDCCrawler:
    """제주특별자치도개발공사 통합검색 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    def _fetch_page(self, keyword, page):
        """통합검색 게시물 결과 한 페이지를 가져옵니다."""
        params = {
            "q": keyword,
            "type": "board",
            "page": page,
        }
        response = self.session.get(
            f"{BASE_URL}/help/search.htm",
            params=params,
            timeout=15,
        )
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        # 결과 파싱: p.text 안에 <a>(breadcrumb), 제목(text), <br>, 날짜(text) 순서
        items = []
        p_tags = soup.select("p.text")
        for p_tag in p_tags:
            link = p_tag.select_one("a[href*='act=view&seq=']")
            if not link:
                continue

            href = link.get("href", "")
            detail_url = f"{BASE_URL}{href}" if href.startswith("/") else href

            # p.text 안의 텍스트 노드에서 제목과 날짜 추출
            text_nodes = []
            for child in p_tag.children:
                if isinstance(child, NavigableString):
                    text = child.strip()
                    if text:
                        text_nodes.append(text)

            title = text_nodes[0] if text_nodes else ""
            # 날짜: YYYY-MM-DD 형식 찾기
            date_text = ""
            for node in text_nodes:
                match = re.search(r'\d{4}-\d{2}-\d{2}', node)
                if match:
                    date_text = match.group(0)
                    break

            if title:
                items.append({
                    "number": "",
                    "title": title.rstrip("…").strip(),
                    "date": date_text,
                    "url": detail_url,
                    "organization": "",
                })

        # 다음 페이지 존재 여부
        has_next = len(items) >= 10
        return items, has_next

    def search(self, keyword="", max_pages=10):
        """게시물을 검색합니다. 통합검색이므로 키워드가 필요합니다."""
        if not keyword:
            keyword = " "  # 빈 키워드면 공백으로 대체

        all_items = []
        seen_urls = set()

        for page in range(1, max_pages + 1):
            items, has_next = self._fetch_page(keyword, page)
            for item in items:
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    all_items.append(item)
            print(f"  [Page {page}] {len(items)}건 수집 (전체 {len(all_items)}건)")
            if not has_next or not items:
                break

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[제주개발공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = JPDCCrawler()
    print("=== '공고' 검색 (2페이지) ===")
    results = crawler.search("공고", max_pages=2)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['url'][:60]}")
