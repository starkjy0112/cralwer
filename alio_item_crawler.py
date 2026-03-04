# -*- coding: utf-8 -*-
"""
알리오(ALIO) 물자구매 크롤러
344개 기관별 입찰공고 검색 (async 병렬 처리)
"""
import asyncio
import aiohttp
from playwright.async_api import async_playwright


class AlioItemCrawler:
    """알리오 물자구매 크롤러"""

    def __init__(self, concurrency: int = 50):
        self.base_url = "https://www.alio.go.kr"
        self.api_url = f"{self.base_url}/item/itemReportListSusi.json"
        self.cookies = None
        self.concurrency = concurrency
        self.org_ids = None  # 기관 ID 목록

    async def _get_cookies(self):
        """Playwright로 쿠키 획득"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(f"{self.base_url}/item/itemOrganList.do?reportFormRootNo=B1030")
            await asyncio.sleep(2)

            cookies = await context.cookies()
            self.cookies = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

            await browser.close()

        return self.cookies

    async def _scan_org_ids(self):
        """유효한 기관 ID 스캔 (C0001 ~ C1200)"""
        if not self.cookies:
            await self._get_cookies()

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Cookie": self.cookies,
            "Content-Type": "application/json",
        }

        valid_ids = []
        semaphore = asyncio.Semaphore(self.concurrency)

        async def check_id(session, apba_id):
            async with semaphore:
                payload = {
                    "pageNo": 1,
                    "apbaId": apba_id,
                    "apbaType": "A2005",
                    "reportFormRootNo": "B1030",
                    "search_word": "",
                    "search_flag": "title"
                }
                try:
                    async with session.post(
                        self.api_url,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as res:
                        data = await res.json()
                        total = data.get("data", {}).get("page", {}).get("totalCount", 0)
                        if total > 0:
                            return apba_id
                except:
                    pass
                return None

        print("[1] 기관 ID 스캔 중...")

        async with aiohttp.ClientSession() as session:
            tasks = [check_id(session, f"C{str(i).zfill(4)}") for i in range(1, 2001)]
            results = await asyncio.gather(*tasks)
            valid_ids = [r for r in results if r]

        self.org_ids = valid_ids
        print(f"[완료] {len(valid_ids)}개 기관 발견")
        return valid_ids

    async def _call_api_async(self, session, headers, apba_id: str, keyword: str, page_no: int):
        """API 비동기 호출"""
        payload = {
            "pageNo": page_no,
            "apbaId": apba_id,
            "apbaType": "A2005",
            "reportFormRootNo": "B1030",
            "search_word": keyword,
            "search_flag": "title",
            "bid_type": "",
            "enfc_istt": ""
        }

        try:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as res:
                data = await res.json()
                return apba_id, page_no, data
        except Exception as e:
            return apba_id, page_no, None

    async def _search_org_async(self, session, headers, apba_id: str, keyword: str, max_pages: int = 100):
        """특정 기관 검색"""
        results = []

        # 첫 페이지로 전체 수 확인
        _, _, data = await self._call_api_async(session, headers, apba_id, keyword, 1)

        if not data or data.get("status") != "success":
            return results

        page_info = data.get("data", {}).get("page", {})
        total_count = page_info.get("totalCount", 0)
        total_pages = page_info.get("totalPage", 1)

        if total_count == 0:
            return results

        # 첫 페이지 결과 추가
        items = data.get("data", {}).get("result", [])
        for item in items:
            disclosure_no = item.get("disclosureNo", "")
            results.append({
                "apba_id": apba_id,
                "title": item.get("title", ""),
                "date": item.get("idate", ""),
                "disclosure_no": disclosure_no,
                "bid_type": item.get("bidType", ""),
                "url": f"https://www.alio.go.kr/item/itemReport.do?seq={disclosure_no}&disclosureNo={disclosure_no}" if disclosure_no else "",
            })

        # 나머지 페이지 (최대 max_pages까지)
        pages_to_fetch = min(total_pages, max_pages)
        if pages_to_fetch > 1:
            tasks = [
                self._call_api_async(session, headers, apba_id, keyword, page_no)
                for page_no in range(2, pages_to_fetch + 1)
            ]
            responses = await asyncio.gather(*tasks)

            for _, _, page_data in responses:
                if page_data and page_data.get("status") == "success":
                    items = page_data.get("data", {}).get("result", [])
                    for item in items:
                        disclosure_no = item.get("disclosureNo", "")
                        results.append({
                            "apba_id": apba_id,
                            "title": item.get("title", ""),
                            "date": item.get("idate", ""),
                            "disclosure_no": disclosure_no,
                            "bid_type": item.get("bidType", ""),
                            "url": f"https://www.alio.go.kr/item/itemReport.do?seq={disclosure_no}&disclosureNo={disclosure_no}" if disclosure_no else "",
                        })

        return results

    async def _search_async(self, keyword: str = "", max_pages: int = 100):
        """모든 기관에서 키워드 검색"""
        if not self.cookies:
            print("[1] 쿠키 획득 중...")
            await self._get_cookies()

        if not self.org_ids:
            await self._scan_org_ids()

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Cookie": self.cookies,
            "Content-Type": "application/json",
            "Referer": f"{self.base_url}/item/itemOrganList.do",
        }

        all_results = []
        semaphore = asyncio.Semaphore(self.concurrency)

        async def search_with_semaphore(session, apba_id):
            async with semaphore:
                return await self._search_org_async(session, headers, apba_id, keyword, max_pages)

        print(f"[2] {len(self.org_ids)}개 기관 검색 중 (키워드: '{keyword or '전체'}')...")

        async with aiohttp.ClientSession() as session:
            tasks = [search_with_semaphore(session, apba_id) for apba_id in self.org_ids]
            results_list = await asyncio.gather(*tasks)

            for results in results_list:
                all_results.extend(results)

        print(f"[완료] 총 {len(all_results)}건")
        return all_results

    def search(self, keyword: str = "", max_pages: int = 100):
        """
        물자구매 입찰공고 검색

        Args:
            keyword: 검색 키워드 (공고명)
            max_pages: 기관당 최대 페이지 수

        Returns:
            검색 결과 리스트
        """
        return asyncio.run(self._search_async(keyword, max_pages))


def search_alio_item(keyword: str = "", max_pages: int = 100):
    """간단한 검색 함수"""
    crawler = AlioItemCrawler()
    return crawler.search(keyword, max_pages)


def main():
    """테스트 실행"""
    import sys

    keyword = sys.argv[1] if len(sys.argv) > 1 else ""

    print(f"\n{'='*60}")
    print(f" 알리오 물자구매 검색 (344개 기관)")
    print(f" 키워드: {keyword or '전체'}")
    print(f"{'='*60}\n")

    results = search_alio_item(keyword, max_pages=10)

    print(f"\n{'='*60}")
    print(f" 검색 결과: {len(results)}건")
    print(f"{'='*60}\n")

    for i, r in enumerate(results[:20], 1):
        print(f"{i}. [{r['apba_id']}] {r['title']}")
        print(f"   날짜: {r['date']}")
        print()

    if len(results) > 20:
        print(f"... 외 {len(results) - 20}건")


if __name__ == "__main__":
    main()
