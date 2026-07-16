# -*- coding: utf-8 -*-
"""
충청남도개발공사 (cndc) - xlsx 35행
6개 게시판 합산.
"""
import math
import re
import time
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


class CNDCCrawler:
    """충청남도개발공사 다게시판 통합 크롤러."""

    BASE_URL = "https://www.cndc.kr"
    LIST_URL = f"{BASE_URL}/bbs/list.do"
    VIEW_URL = f"{BASE_URL}/bbs/view.do"
    PAGE_SIZE = 10

    BOARDS = [
        ('2404080009', '입찰공고'),      # xlsx 35행 지정
    ]

    MAX_RETRIES = 5
    PAGE_DELAY = 0.3

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

    def _fetch(self, key, page):
        url = f"{self.LIST_URL}?key={key}&pageIndex={page}"
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.get(url, timeout=30)
                r.raise_for_status()
                r.encoding = 'utf-8'
                return BeautifulSoup(r.text, 'lxml'), r.text
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.5 * (attempt + 1))
        return None, ''

    def _get_total(self, html):
        m = re.search(r'전체\s*<[^>]*>(\d+)', html)
        return int(m.group(1)) if m else 0

    def _parse_rows(self, soup, board_name, key):
        results = []
        if not soup:
            return results
        # 일반 게시판: tbody tr / 갤러리: ul.gallery li 등
        for tr in soup.select('tbody tr'):
            tds = tr.find_all('td')
            if len(tds) < 2:
                continue
            a = tr.select_one('a[onclick*="goView"], a[onclick*="VIEW"], a[href*="view.do"]')
            if not a:
                continue
            onclick = a.get('onclick', '') or ''
            href = a.get('href', '') or ''
            m = re.search(r"goView\(['\"]?(\d+)", onclick)
            pst_sn = m.group(1) if m else ''
            if not pst_sn:
                m = re.search(r'pstSn=(\d+)', href)
                pst_sn = m.group(1) if m else ''
            if not pst_sn:
                continue
            url = f"{self.VIEW_URL}?key={key}&pstSn={pst_sn}"
            title = a.get_text(' ', strip=True)
            title = re.sub(r'\s+', ' ', title).strip()
            if not title or len(title) < 2:
                continue
            date = ''
            for td in tds:
                t = td.get_text(' ', strip=True)
                m2 = re.search(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', t)
                if m2:
                    date = f"{m2.group(1)}-{m2.group(2).zfill(2)}-{m2.group(3).zfill(2)}"
                    break
            results.append({
                'title': title, 'date': date, 'url': url,
                'organization': board_name, 'number': pst_sn,
            })
        # 갤러리/카드 구조 (ul.board-list li) - 포토갤러리 등
        if not results:
            for li in soup.select('ul.board-list li, ul.gallery li, ul.gall li, .gallery-list li'):
                a = li.select_one('a[onclick*="goView"], a[onclick*="VIEW"]')
                if not a:
                    continue
                m = re.search(r"goView\(['\"]?(\d+)", a.get('onclick', ''))
                if not m:
                    continue
                pst_sn = m.group(1)
                url = f"{self.VIEW_URL}?key={key}&pstSn={pst_sn}"
                # 제목 정리: 링크 텍스트에 날짜/조회수 붙어있으면 첫 부분만
                full_text = a.get_text(' ', strip=True)
                # "제목YYYY-MM-DD조회수XXX" 형태 → 날짜 앞까지 자름
                title_m = re.match(r'(.+?)\d{4}[-./]\d{1,2}[-./]\d{1,2}', full_text)
                title = title_m.group(1).strip() if title_m else full_text[:100]
                # 날짜 추출
                date = ''
                date_m = re.search(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', full_text)
                if date_m:
                    date = f"{date_m.group(1)}-{date_m.group(2).zfill(2)}-{date_m.group(3).zfill(2)}"
                if not title or len(title) < 2:
                    continue
                results.append({
                    'title': title, 'date': date, 'url': url,
                    'organization': board_name, 'number': pst_sn,
                })
        return results

    def _crawl_board(self, board_tuple):
        key, board_name = board_tuple
        results = []
        seen = set()
        first_soup, first_html = self._fetch(key, 1)
        if not first_soup:
            return results
        total = self._get_total(first_html)
        last_p = max(1, math.ceil(total / self.PAGE_SIZE))
        for it in self._parse_rows(first_soup, board_name, key):
            if it['url'] not in seen:
                seen.add(it['url'])
                results.append(it)
        empty_streak = 0
        for page in range(2, last_p + 1):
            time.sleep(self.PAGE_DELAY)
            soup, _ = self._fetch(key, page)
            rows = self._parse_rows(soup, board_name, key)
            for it in rows:
                if it['url'] not in seen:
                    seen.add(it['url'])
                    results.append(it)
            if not rows:
                empty_streak += 1
                if empty_streak >= 5:
                    break
            else:
                empty_streak = 0
        return results

    def search(self, keyword='', max_pages=999, start_date=None, end_date=None):
        all_results = {}
        for board in self.BOARDS:
            try:
                items = self._crawl_board(board)
                for r in items:
                    if r['url'] not in all_results:
                        all_results[r['url']] = r
                print(f"  [{board[1]}] {len(items)}건", flush=True)
            except Exception as e:
                print(f"  [{board[1]}] 에러: {str(e)[:60]}", flush=True)
            time.sleep(1.0)

        items = list(all_results.values())
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        items = [it for it in items
                 if not it['date'] or (start_date <= it['date'][:10] <= end_date)]
        items.sort(key=lambda x: x['date'] or '', reverse=True)
        print(f"[충청남도개발공사] 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    import urllib3
    urllib3.disable_warnings()
    c = CNDCCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    from collections import Counter
    for k, v in Counter(it['organization'] for it in items).most_common():
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
