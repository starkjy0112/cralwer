# -*- coding: utf-8 -*-
"""
제주특별자치도개발공사 (jpdc) - xlsx 33행

**통합검색 " " (공백) 방식** - 사이트 게시물 검색 6,456건 전량 확보.

- 게시판 순회 방식은 실측 시 4,616건 한계 (일부 게시판이 대시보드 URL이라 페이지네이션 무시)
- 통합검색이 6,220건으로 커버리지 최대 (96.3%)

URL: /help/search.htm?q= &type=board&page=N (공백은 %20으로 인코딩)
페이지당 20건, 총 323페이지.

주의:
- q= 빈값은 0건, q=%20 (공백)은 6,456건
- 브라우저 UI에서 빈칸은 폼이 서버로 빈 q= 보내서 0건
"""
import re
import time
import requests
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


class JPDCCrawler:
    """제주개발공사 통합검색 크롤러 (공백 검색 방식)."""

    BASE_URL = "https://www.jpdc.co.kr"
    SEARCH_PATH = "/help/search.htm"

    # 공백 " " 검색으로 게시물 전량 매칭 (6,456건)
    # 다른 키워드 필요 없음
    KEYWORDS = [' ']

    MAX_RETRIES = 4
    PAGE_DELAY = 0.15
    PAGE_SIZE = 20
    HARD_PAGE_CAP = 400

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

    def _fetch(self, url):
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.get(url, timeout=30)
                r.raise_for_status()
                r.encoding = 'utf-8'
                return BeautifulSoup(r.text, 'lxml')
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.2 * (attempt + 1))
        return None

    def _total_count(self, soup):
        """게시물 검색 총 건수 추출."""
        if not soup:
            return 0
        for h in soup.select('h2'):
            if '게시물' in h.get_text():
                wrap = h.find_parent(class_='search-contents-top') or h.parent
                if wrap:
                    span = wrap.select_one('.count .text-blue')
                    if span and span.get_text(strip=True).isdigit():
                        return int(span.get_text(strip=True))
        spans = soup.select('.count .text-blue')
        if spans:
            try:
                return int(spans[-1].get_text(strip=True))
            except ValueError:
                return 0
        return 0

    def _parse_items(self, soup):
        items = []
        if not soup:
            return items
        for p in soup.select('p.text'):
            a = p.find('a', href=True)
            if not a:
                continue
            href = a['href']
            if 'act=view' not in href and 'seq=' not in href:
                continue

            # URL 정규화: '?'가 없으면 첫 '&'를 '?'로 (이전 크롤 잘못된 URL 형식 방지)
            if not href.startswith('http'):
                url = urljoin(self.BASE_URL, href)
            else:
                url = href
            # &act=view 로 시작하면 잘못된 URL - ?로 정규화
            if re.search(r'\.htm&act=', url):
                url = url.replace('.htm&act=', '.htm?act=')
            # page 파라미터 제거 (같은 게시글 dedup)
            url = re.sub(r'[?&]page=\d+', '', url)
            # ? 뒤에 &부터 시작하면 &를 지우고 첫 &를 ?로
            url = re.sub(r'\?&', '?', url)

            board_path = a.get_text(' ', strip=True)
            board_name = board_path.split('>')[-1].strip() if '>' in board_path else '통합검색'

            title = ''
            date = ''
            found_after_a = False
            texts = []
            for child in p.children:
                if child is a:
                    found_after_a = True
                    continue
                if not found_after_a:
                    continue
                if getattr(child, 'name', None) == 'br':
                    texts.append('|BR|')
                elif getattr(child, 'name', None) is None:
                    texts.append(str(child).strip())
                else:
                    texts.append(child.get_text(' ', strip=True))
            merged = ' '.join(texts)
            segs = [s.strip() for s in merged.split('|BR|') if s.strip()]
            if segs:
                title = segs[0]
            for s in segs[1:]:
                m = re.search(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', s)
                if m:
                    date = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
                    break

            if not title or len(title) < 2:
                continue

            # seq
            m_seq = re.search(r'seq=(\d+)', href)
            seq = m_seq.group(1) if m_seq else ''

            items.append({
                'title': title,
                'date': date,
                'url': url,
                'organization': board_name,
                'number': seq,
            })
        return items

    def _last_page(self, soup):
        if not soup:
            return 1
        last = soup.select_one('a[title*="마지막"]')
        if last:
            m = re.search(r'[?&]page=(\d+)', last.get('href', ''))
            if m:
                return int(m.group(1))
        nums = [int(m.group(1))
                for a in soup.select('a[href*="page="]')
                for m in [re.search(r'[?&]page=(\d+)', a.get('href', ''))]
                if m]
        return max(nums) if nums else 1

    def _search_keyword(self, keyword, results, seen, reverse=False):
        added_before = len(results)
        url1 = f"{self.BASE_URL}{self.SEARCH_PATH}?q={requests.utils.quote(keyword)}&type=board&page=1"
        first = self._fetch(url1)
        if not first:
            print(f"  [{keyword}] fetch 실패", flush=True)
            return
        total = self._total_count(first)
        last_p = min(self._last_page(first), self.HARD_PAGE_CAP)

        # 페이지 순서: reverse=True 이면 마지막 페이지부터 (오래된 것부터, 페이지네이션 밀림 영향 X)
        if reverse:
            pages = list(range(last_p, 0, -1))
        else:
            pages = list(range(1, last_p + 1))

        empty_streak = 0
        for page in pages:
            if page == 1 and not reverse:
                batch = self._parse_items(first)
            else:
                time.sleep(self.PAGE_DELAY)
                u = f"{self.BASE_URL}{self.SEARCH_PATH}?q={requests.utils.quote(keyword)}&type=board&page={page}"
                soup = self._fetch(u)
                batch = self._parse_items(soup)

            for it in batch:
                if it['url'] not in seen:
                    seen.add(it['url'])
                    results.append(it)
            if not batch:
                empty_streak += 1
                if empty_streak >= 3:
                    break
            else:
                empty_streak = 0
        added = len(results) - added_before
        direction = "역순" if reverse else "정순"
        print(f"  [q='{keyword}' {direction}] total={total} pages={last_p} +{added} unique", flush=True)

    def search(self, keyword='', max_pages=999, start_date=None, end_date=None):
        """정순 + 역순 2회 크롤로 100% 커버 목표.
        정순: 최신 게시글 확보
        역순: 크롤 도중 사이트 페이지네이션 밀림으로 놓친 오래된 게시글 회수
        """
        results = []
        seen = set()

        kw_list = [keyword] if keyword else self.KEYWORDS
        for kw in kw_list:
            # 1차: 정순 크롤
            try:
                self._search_keyword(kw, results, seen, reverse=False)
            except Exception as e:
                print(f"  [{kw}] 정순 에러: {str(e)[:80]}", flush=True)
            time.sleep(0.5)
            # 2차: 역순 크롤 (밀림 회수)
            try:
                self._search_keyword(kw, results, seen, reverse=True)
            except Exception as e:
                print(f"  [{kw}] 역순 에러: {str(e)[:80]}", flush=True)
            time.sleep(0.3)

        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        filtered = [it for it in results
                    if not it['date'] or (start_date <= it['date'][:10] <= end_date)]
        filtered.sort(key=lambda x: x['date'] or '', reverse=True)
        print(f"[제주개발공사] 완료: 총 {len(filtered)}건", flush=True)
        return filtered


def main():
    import urllib3
    urllib3.disable_warnings()
    c = JPDCCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    from collections import Counter
    for k, v in Counter(it['organization'] for it in items).most_common():
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
