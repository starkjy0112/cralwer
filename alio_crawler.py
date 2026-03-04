# -*- coding: utf-8 -*-
"""
알리오(ALIO) 입찰공고 크롤러
쿠키 기반 API 호출 방식 (async 병렬 처리)
"""
import asyncio
import aiohttp
import time
import requests
from playwright.async_api import async_playwright

# 전역 쿠키 캐시 (모든 인스턴스가 공유)
_cookie_cache = {
    "cookies": None,
    "expires": 0
}
COOKIE_TTL = 3600  # 1시간


class AlioCrawler:
    """알리오 입찰공고 크롤러"""

    def __init__(self, concurrency: int = 100):
        self.base_url = "https://www.alio.go.kr"
        self.api_url = f"{self.base_url}/occasional/findBidList.json"
        self.cookies = None
        self.concurrency = concurrency  # 동시 요청 수

    async def _get_cookies(self):
        """쿠키 획득 (캐시 우선, requests 시도, Playwright 폴백)"""
        global _cookie_cache

        # 1. 캐시 확인
        if _cookie_cache["cookies"] and time.time() < _cookie_cache["expires"]:
            self.cookies = _cookie_cache["cookies"]
            return self.cookies

        # 2. requests로 빠르게 시도
        try:
            session = requests.Session()
            resp = session.get(f"{self.base_url}/occasional/bidList.do", timeout=10)
            if resp.status_code == 200 and session.cookies:
                self.cookies = "; ".join([f"{c.name}={c.value}" for c in session.cookies])
                _cookie_cache["cookies"] = self.cookies
                _cookie_cache["expires"] = time.time() + COOKIE_TTL
                return self.cookies
        except Exception:
            pass

        # 3. Playwright 폴백
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(f"{self.base_url}/occasional/bidList.do")
            await asyncio.sleep(2)

            cookies = await context.cookies()
            self.cookies = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

            await browser.close()

        _cookie_cache["cookies"] = self.cookies
        _cookie_cache["expires"] = time.time() + COOKIE_TTL
        return self.cookies

    async def _call_api_async(self, session: aiohttp.ClientSession, keyword: str, page_no: int):
        """API 비동기 호출"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Cookie": self.cookies,
            "Referer": f"{self.base_url}/occasional/bidList.do",
            "Accept": "application/json"
        }

        params = {
            "type": "title",
            "word": keyword,
            "pageNo": str(page_no),
            "area": ""
        }

        try:
            async with session.get(self.api_url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as res:
                data = await res.json()
                return page_no, data
        except Exception as e:
            print(f"[오류] 페이지 {page_no}: {e}")
            return page_no, None

    async def _search_async(self, keyword: str = "", max_pages: int = 1):
        """비동기 검색"""
        # 쿠키 없으면 획득 (캐시 우선 확인)
        if not self.cookies:
            # 캐시에 있으면 바로 사용
            if _cookie_cache["cookies"] and time.time() < _cookie_cache["expires"]:
                self.cookies = _cookie_cache["cookies"]
            else:
                print("[1] 쿠키 획득 중...")
                await self._get_cookies()

        results = []
        semaphore = asyncio.Semaphore(self.concurrency)

        async def fetch_with_semaphore(session, page_no):
            async with semaphore:
                return await self._call_api_async(session, keyword, page_no)

        async with aiohttp.ClientSession() as session:
            # 첫 페이지로 총 페이지 수 확인
            _, first_data = await self._call_api_async(session, keyword, 1)
            if not first_data or first_data.get("status") != "success":
                print("[오류] 첫 페이지 조회 실패")
                return results

            # 총 페이지 수 확인
            page_info = first_data.get("data", {}).get("page", {})
            total_count = page_info.get("totalCount", 0)
            total_pages = page_info.get("totalPage", 1)
            actual_pages = min(max_pages, total_pages)

            print(f"[2] 총 {total_count}건, {actual_pages}페이지 병렬 조회 중...")

            # 첫 페이지 결과 추가
            items = first_data.get("data", {}).get("result", [])
            for item in items:
                seq = item.get("seq", "")
                results.append({
                    "title": item.get("rtitle", ""),
                    "organization": item.get("pname", ""),
                    "deadline": item.get("bidInfoEndDt", ""),
                    "date": item.get("bdate", ""),
                    "seq": seq,
                    "url": f"https://www.alio.go.kr/occasional/bidDtl.do?seq={seq}" if seq else "",
                })

            # 나머지 페이지 병렬 조회
            if actual_pages > 1:
                tasks = [fetch_with_semaphore(session, page_no) for page_no in range(2, actual_pages + 1)]
                responses = await asyncio.gather(*tasks)
            else:
                responses = []

        # 페이지 순서대로 정렬
        responses.sort(key=lambda x: x[0])

        for page_no, data in responses:
            if data is None:
                continue

            if data.get("status") != "success":
                print(f"[오류] 페이지 {page_no}: {data.get('message', '알 수 없는 오류')}")
                continue

            items = data.get("data", {}).get("result", [])

            if not items:
                continue

            for item in items:
                seq = item.get("seq", "")
                results.append({
                    "title": item.get("rtitle", ""),
                    "organization": item.get("pname", ""),
                    "deadline": item.get("bidInfoEndDt", ""),
                    "date": item.get("bdate", ""),
                    "seq": seq,
                    "url": f"https://www.alio.go.kr/occasional/bidDtl.do?seq={seq}" if seq else "",
                })

        print(f"[완료] 총 {len(results)}건")
        return results

    def search(self, keyword: str = "", max_pages: int = 1):
        """
        알리오 입찰공고 검색 (동기 래퍼)

        Args:
            keyword: 검색 키워드 (공고명)
            max_pages: 최대 페이지 수

        Returns:
            검색 결과 리스트
        """
        return asyncio.run(self._search_async(keyword, max_pages))


def search_alio(keyword: str = "", max_pages: int = 1):
    """간단한 검색 함수"""
    crawler = AlioCrawler()
    return crawler.search(keyword, max_pages)


def main():
    """테스트 실행"""
    import sys

    keyword = sys.argv[1] if len(sys.argv) > 1 else ""

    print(f"\n{'='*60}")
    print(f" 알리오 입찰공고 검색 (async)")
    print(f" 키워드: {keyword or '전체'}")
    print(f"{'='*60}\n")

    results = search_alio(keyword, max_pages=1)

    print(f"\n{'='*60}")
    print(f" 검색 결과: {len(results)}건")
    print(f"{'='*60}\n")

    for i, r in enumerate(results[:10], 1):
        print(f"{i}. {r['title']}")
        print(f"   기관: {r['organization']}")
        print(f"   마감: {r['deadline']}")
        print()


if __name__ == "__main__":
    main()
