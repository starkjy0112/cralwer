# -*- coding: utf-8 -*-
"""
성남도시개발공사 (isdc) - xlsx 29행 통합검색
https://www.isdc.co.kr/guidance/search.asp

통합검색은 카테고리별 미리보기(각 5건)만 보여준다.
카테고리 상세(searchBbsList.asp?HiddenBbsNo=N)로 페이지네이션(HiddenPageNum) 순회.
빈 검색어(searchTxt=)로 카테고리 전체 목록을 가져올 수 있음.
"""
import re
import time
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


class ISDCCrawler:
    """성남도시개발공사 통합검색 크롤러 (카테고리별 순회)"""

    BASE_URL = "https://www.isdc.co.kr"
    SEARCH_URL = f"{BASE_URL}/guidance/searchBbsList.asp"

    # (HiddenBbsNo, 카테고리명)
    CATEGORIES = [
        (1, '입찰정보'),
        (2, '공지사항'),
        (3, '보도자료'),
        (4, '행사안내'),
        (6, '계약정보'),
        (50, '분양공고'),
        (58, '홍보자료'),
        (60, '정보목록'),
        (61, '임대공고'),
        (73, '대금지급'),
        (74, '계약관련정보'),
        (75, '사전정보공표'),
        (77, '채용공고'),
    ]

    WORKERS = 6
    PAGE_SIZE = 10  # 서버 고정
    MAX_RETRIES = 3
    MAX_PAGES = 500  # 안전장치

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.verify = False

    def _fetch_page(self, bbs_no, page):
        url = f"{self.SEARCH_URL}?HiddenBbsNo={bbs_no}&HiddenPageNum={page}&searchTxt="
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.get(url, timeout=25)
                r.raise_for_status()
                r.encoding = 'utf-8'
                return BeautifulSoup(r.text, 'lxml')
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1 + attempt)
        return None

    def _get_last_page(self, soup):
        """페이징 영역에서 마지막 페이지 번호 추출"""
        if not soup:
            return 1
        # pagingLast의 onclick에서 ChagePageNum(N, ...) 뽑기
        last = soup.select_one('a.pagingLast')
        if last:
            m = re.search(r"ChagePageNum\(\s*(\d+)", last.get('onclick', ''))
            if m:
                return int(m.group(1))
        # fallback: 페이지 링크 중 최대값
        max_p = 1
        for a in soup.select('div.pageWrap a'):
            m = re.search(r"ChagePageNum\(\s*(\d+)", a.get('onclick', ''))
            if m:
                max_p = max(max_p, int(m.group(1)))
        for span in soup.select('div.pageWrap span'):
            t = span.get_text(strip=True)
            if t.isdigit():
                max_p = max(max_p, int(t))
        return max_p

    def _parse_rows(self, soup, cat_name):
        results = []
        if not soup:
            return results
        # 각 li > dl > dt.tit > a (title) + span(date)
        for li in soup.select('ul.totalSchList > li'):
            a = li.select_one('dt.tit a')
            if not a:
                continue
            # 제목에 <font class='kwd01'></font> 노이즈가 섞여 있으므로 텍스트만 뽑고 공백 정리
            title = a.get_text('', strip=True).strip()
            title = re.sub(r'\s+', ' ', title)
            if not title:
                continue
            href = a.get('href', '')
            if not href:
                continue
            url = href if href.startswith('http') else self.BASE_URL + href
            date_el = li.select_one('dt.tit span')
            date = ''
            if date_el:
                t = date_el.get_text(strip=True)
                m = re.search(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', t)
                if m:
                    date = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
                else:
                    date = t
            results.append({
                'title': title,
                'date': date,
                'url': url,
                'organization': cat_name,
                'number': '',
            })
        return results

    def _crawl_category(self, cat_tuple):
        bbs_no, name = cat_tuple
        results = []
        seen = set()

        soup = self._fetch_page(bbs_no, 1)
        if not soup:
            return results
        last_page = min(self._get_last_page(soup), self.MAX_PAGES)
        for it in self._parse_rows(soup, name):
            if it['url'] not in seen:
                seen.add(it['url'])
                results.append(it)

        empty_streak = 0
        for page in range(2, last_page + 1):
            soup = self._fetch_page(bbs_no, page)
            items = self._parse_rows(soup, name)
            new = [it for it in items if it['url'] not in seen]
            if not new:
                empty_streak += 1
                if empty_streak >= 3:
                    break
                continue
            empty_streak = 0
            for it in new:
                seen.add(it['url'])
                results.append(it)
        return results

    def search(self, keyword='', max_pages=999, start_date=None, end_date=None):
        all_results = {}
        with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
            futures = {executor.submit(self._crawl_category, c): c
                       for c in self.CATEGORIES}
            for future in as_completed(futures):
                cat = futures[future]
                try:
                    got = future.result()
                    for r in got:
                        if r['url'] not in all_results:
                            all_results[r['url']] = r
                    print(f"  [{cat[1]}] {len(got)}건", flush=True)
                except Exception as e:
                    print(f"  [{cat[1]}] 에러: {str(e)[:60]}", flush=True)

        items = list(all_results.values())
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        items = [it for it in items
                 if not it['date'] or (start_date <= it['date'][:10] <= end_date)]
        items.sort(key=lambda x: x['date'] or '', reverse=True)
        print(f"[성남도시개발공사] 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    import urllib3
    urllib3.disable_warnings()
    c = ISDCCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    from collections import Counter
    for k, v in Counter(it['organization'] for it in items).most_common():
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
