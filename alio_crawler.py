# -*- coding: utf-8 -*-
"""
알리오(ALIO) 입찰공고 크롤러
쿠키 기반 API 호출 방식 (async 병렬 처리)
"""
import asyncio
import aiohttp
import time
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from playwright.async_api import async_playwright

# 전역 쿠키 캐시 (모든 인스턴스가 공유)
_cookie_cache = {
    "cookies": None,
    "expires": 0
}
COOKIE_TTL = 3600  # 1시간


class AlioCrawler:
    """알리오 입찰공고 크롤러"""

    def __init__(self, concurrency: int = 10):
        self.base_url = "https://www.alio.go.kr"
        self.api_url = f"{self.base_url}/occasional/findBidList.json"
        self.cookies = None
        self.concurrency = concurrency  # 동시 요청 수 (서버 부하 방지)

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

    async def _call_api_async(self, session: aiohttp.ClientSession, keyword: str, page_no: int, retries: int = 2):
        """API 비동기 호출 (재시도 포함)"""
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

        last_err = None
        for attempt in range(retries + 1):
            try:
                async with session.get(self.api_url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as res:
                    data = await res.json()
                    return page_no, data
            except Exception as e:
                last_err = e
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
        return page_no, None

    async def _search_async(self, keyword: str = "", max_pages: int = 1, start_date=None, end_date=None):
        """비동기 검색 (배치 + early stop)"""
        # 날짜 기본값
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        # 쿠키 없으면 획득
        if not self.cookies:
            if _cookie_cache["cookies"] and time.time() < _cookie_cache["expires"]:
                self.cookies = _cookie_cache["cookies"]
            else:
                print("[1] 쿠키 획득 중...")
                await self._get_cookies()

        results = []

        def parse_items(items):
            parsed = []
            for item in items:
                seq = item.get("seq", "")
                parsed.append({
                    "title": item.get("rtitle", ""),
                    "organization": item.get("pname", ""),
                    "deadline": item.get("bidInfoEndDt", ""),
                    "date": item.get("bdate", ""),
                    "seq": seq,
                    "url": f"https://www.alio.go.kr/occasional/bidDtl.do?seq={seq}" if seq else "",
                })
            return parsed

        def in_range(item):
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            return d and start_date <= d <= end_date

        def is_too_old(item):
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            return d and d < start_date

        async with aiohttp.ClientSession() as session:
            # 첫 페이지로 총 페이지 수 확인
            _, first_data = await self._call_api_async(session, keyword, 1)
            if not first_data or first_data.get("status") != "success":
                print("[오류] 첫 페이지 조회 실패")
                return results

            page_info = first_data.get("data", {}).get("page", {})
            total_count = page_info.get("totalCount", 0)
            total_pages = page_info.get("totalPage", 1)
            actual_pages = min(max_pages, total_pages)

            print(f"[2] 총 {total_count}건, 최대 {actual_pages}페이지 (배치 조회 + early stop)")

            # 첫 페이지 결과
            first_items = parse_items(first_data.get("data", {}).get("result", []))
            for item in first_items:
                if in_range(item):
                    results.append(item)

            # 첫 페이지에 이미 start_date보다 오래된 게 있으면 거기서 중단
            if any(is_too_old(item) for item in first_items):
                print(f"[완료] {len(results)}건 (early stop at page 1)")
                return results

            # 배치 단위로 받아가며 early stop 검사
            BATCH_SIZE = self.concurrency * 2  # 한 번에 20페이지씩 (concurrency=10)
            page = 2
            stop = False
            failed_pages = []

            while page <= actual_pages and not stop:
                batch_end = min(page + BATCH_SIZE, actual_pages + 1)
                tasks = [self._call_api_async(session, keyword, p) for p in range(page, batch_end)]
                responses = await asyncio.gather(*tasks)
                responses.sort(key=lambda x: x[0])

                for page_no, data in responses:
                    if data is None or data.get("status") != "success":
                        failed_pages.append(page_no)
                        continue
                    items_raw = data.get("data", {}).get("result", [])
                    parsed = parse_items(items_raw)

                    page_has_too_old = False
                    for item in parsed:
                        if is_too_old(item):
                            page_has_too_old = True
                            stop = True
                        if in_range(item):
                            results.append(item)
                    # 같은 페이지 안에서 너무 오래된 게 나왔어도, 그 페이지의 in_range는 다 처리됨

                page = batch_end

            # 실패한 페이지 재시도 (한 번 더)
            if failed_pages:
                # stop 이후 페이지는 재시도 안 함 (이미 범위 밖)
                # stop 시점 이전의 실패한 페이지만 재시도
                retry_pages = [p for p in failed_pages if p <= page]
                print(f"[재시도] 실패 페이지 {len(retry_pages)}개")
                for batch_start in range(0, len(retry_pages), self.concurrency):
                    batch = retry_pages[batch_start:batch_start + self.concurrency]
                    tasks = [self._call_api_async(session, keyword, p) for p in batch]
                    responses = await asyncio.gather(*tasks)
                    for page_no, data in responses:
                        if data is None or data.get("status") != "success":
                            continue
                        items_raw = data.get("data", {}).get("result", [])
                        parsed = parse_items(items_raw)
                        for item in parsed:
                            if in_range(item):
                                results.append(item)

        print(f"[완료] {len(results)}건 (조회 페이지 ~{page-1})")
        return results

    def search(self, keyword: str = "", max_pages: int = 1, start_date=None, end_date=None):
        """
        알리오 입찰공고 검색 (동기 래퍼)

        Args:
            keyword: 검색 키워드 (공고명)
            max_pages: 최대 페이지 수

        Returns:
            검색 결과 리스트
        """
        return asyncio.run(self._search_async(keyword, max_pages, start_date=start_date, end_date=end_date))


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
