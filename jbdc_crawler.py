# -*- coding: utf-8 -*-
"""
전북개발공사 (jbdc) - xlsx 32행
통합검색: https://www.jbdc.co.kr/search/board.do?searchWrd=<키워드>

**빈 검색(searchWrd=)이 가능** - 전체 3,216건을 한 번에 반환한다.
따라서 단일 빈 검색으로 전량 수집. (구버전은 다중 키워드였지만 부족했음)

페이지네이션 없이 결과 전량 나옴.
날짜는 리스트에 없고 view 페이지에만 있으므로 date는 빈값으로 둔다.
"""
import re
import ssl
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import quote


class _TLSAdapter(HTTPAdapter):
    """jbdc 서버의 옛 SSL/cipher 호환 어댑터."""
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=0')
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.minimum_version = ssl.TLSVersion.TLSv1
        except Exception:
            pass
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)


# 카테고리 라벨(리스트의 [xxx]) → 조직명 매핑
CATEGORY_MAP = {
    '공지사항': '공지사항',
    '입찰공고': '입찰공고',
    '언론보도': '언론보도',
    '분양임대': '분양임대',
    '포토갤러리': '포토갤러리',
    '자유게시판': '자유게시판',
    '자료실': '자료실',
    'FAQ': 'FAQ',
    'Q&A': 'Q&A',
    '고객참여': '고객참여',
}


class JBDCCrawler:
    """전북개발공사 통합검색 크롤러 (다중 키워드 dedup)."""

    BASE_URL = "https://www.jbdc.co.kr"
    SEARCH_PATH = "/search/board.do"

    # 빈 검색으로 전량 반환됨. 백업으로 몇 개 키워드 유지 (혹시 사이트 변경 대비)
    KEYWORDS = ['']  # 빈 문자열 = 전체 검색

    WORKERS = 1
    MAX_RETRIES = 6
    REQUEST_DELAY = 0.5

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
        })
        self.session.mount("https://", _TLSAdapter(pool_connections=1, pool_maxsize=20))
        self.session.verify = False

    def _fetch(self, url):
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.get(url, timeout=45)
                r.raise_for_status()
                r.encoding = 'utf-8'
                return BeautifulSoup(r.text, 'lxml')
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.5 * (attempt + 1))
        return None

    def _parse_search(self, soup):
        """통합검색 결과 파싱: [카테고리]제목 링크(nttId, bbsId 포함)."""
        results = []
        if not soup:
            return results
        # 검색 결과는 li 안에 <span class="color_b">[카테고리]</span><a href="/search/view.do?...">제목</a>
        for a in soup.select('a[href*="/search/view.do"]'):
            href = a.get('href', '') or ''
            if 'nttId=' not in href:
                continue
            # 카테고리 라벨(같은 li 안의 span)
            parent = a.find_parent('li') or a.parent
            cat_span = parent.select_one('span.color_b') if parent else None
            category = ''
            if cat_span:
                ctxt = cat_span.get_text(strip=True)
                m = re.match(r'\[([^\]]+)\]', ctxt)
                if m:
                    category = m.group(1).strip()
            # 제목
            title = a.get_text(' ', strip=True)
            title = re.sub(r'\s*내용\s*자세히보기\s*$', '', title).strip()
            if not title or len(title) < 2:
                continue
            # nttId, bbsId 추출
            m_ntt = re.search(r'nttId=(\d+)', href)
            m_bbs = re.search(r'bbsId=([A-Za-z0-9_]+)', href)
            if not m_ntt:
                continue
            ntt = m_ntt.group(1)
            bbs = m_bbs.group(1) if m_bbs else ''
            # URL 정규화: searchWrd 제거해서 keyword별 dedup 가능하게
            url = f"{self.BASE_URL}/search/view.do?bbsId={bbs}&nttId={ntt}"
            org = CATEGORY_MAP.get(category, category or '통합검색')
            results.append({
                'title': title,
                'date': '',   # 리스트에는 날짜 없음
                'url': url,
                'organization': org,
                'number': ntt,
                '_bbs': bbs,
            })
        return results

    def _search_keyword(self, keyword):
        url = f"{self.BASE_URL}{self.SEARCH_PATH}?searchWrd={quote(keyword)}"
        soup = self._fetch(url)
        return self._parse_search(soup)

    def search(self, keyword='', max_pages=999, start_date=None, end_date=None):
        all_results = {}
        total_kw = len(self.KEYWORDS)
        for idx, kw in enumerate(self.KEYWORDS, 1):
            try:
                items = self._search_keyword(kw)
                added = 0
                for r in items:
                    key = r['url']
                    if key not in all_results:
                        all_results[key] = r
                        added += 1
                print(f"  [{idx}/{total_kw}] '{kw}' → {len(items)}건 (신규 {added})", flush=True)
            except Exception as e:
                print(f"  [{idx}/{total_kw}] '{kw}' 에러: {str(e)[:60]}", flush=True)
            time.sleep(self.REQUEST_DELAY)

        items = list(all_results.values())
        # 날짜는 리스트에 없으므로 필터를 통과시킴 (date 빈문자열 통과)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        items = [it for it in items
                 if not it['date'] or (start_date <= it['date'][:10] <= end_date)]
        # nttId 내림차순 (최신부터)
        items.sort(key=lambda x: int(x.get('number') or 0), reverse=True)
        print(f"[전북개발공사] 통합검색 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    import urllib3
    urllib3.disable_warnings()
    c = JBDCCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    from collections import Counter
    for k, v in Counter(it['organization'] for it in items).most_common():
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
