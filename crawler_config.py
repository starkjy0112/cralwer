# -*- coding: utf-8 -*-
"""
크롤러 공통 설정 - DB 기반 검색어/URL 로드.

크롤러 코드가 하드코딩 대신 DB에서 검색어/URL 로드하도록 하는 헬퍼.
DB가 비어 있거나 오류 시 파일 기본값(FALLBACK)으로 안전 폴백.

사용법:
    from crawler_config import get_keywords, get_crawler_url, record_link_check

    class MyCrawler:
        def __init__(self):
            self.keywords = get_keywords()  # xlsx 25개 + 사용자 추가
            self.url, self.fallback = get_crawler_url('jbdc') or (self.DEFAULT_URL, None)
"""
import functools
from typing import Optional, Tuple, List


# ---- xlsx 기본 25개 키워드 (DB 실패 시 안전 폴백) ----
DEFAULT_XLSX_KEYWORDS = [
    "기본설계", "실시설계", "기술제안", "제안서", "신기술",
    "공법", "특허", "특정", "발파", "암발파",
    "미진동", "무진동", "암절취", "흙깍기", "절토",
    "토공", "토목", "토건", "제출", "제안",
    "부지조성", "단지조성", "산업단지", "조성공사", "개발사업",
]


@functools.lru_cache(maxsize=1)
def _cached_keywords(_ttl_key: int) -> List[str]:
    """DB 검색어 캐시. _ttl_key로 5분마다 무효화."""
    try:
        import db
        rows = db.get_keywords()
        kws = [r['keyword'] for r in rows]
        return kws if kws else list(DEFAULT_XLSX_KEYWORDS)
    except Exception:
        return list(DEFAULT_XLSX_KEYWORDS)


def get_keywords(include_default: bool = True) -> List[str]:
    """검색어 리스트 반환. include_default=False면 사용자 커스텀만.
    5분 캐시. DB 오류 시 xlsx 기본 25개 폴백."""
    import time
    ttl = int(time.time() // 300)  # 5분마다 캐시 갱신
    kws = _cached_keywords(ttl)
    if include_default:
        return kws
    # 사용자 커스텀만
    try:
        import db
        rows = db.get_keywords()
        return [r['keyword'] for r in rows if not r['is_default']]
    except Exception:
        return []


def get_crawler_url(crawler_id: str, board_key: str = 'default') \
        -> Optional[Tuple[str, Optional[str]]]:
    """DB에서 크롤러 URL 로드. (url, fallback_url) 반환.
    없으면 None → 호출측이 파일 기본값 사용."""
    try:
        import db
        rows = db.get_crawler_urls(crawler_id=crawler_id, active_only=True)
        # 정확한 board_key 매치 우선
        for r in rows:
            if r['board_key'] == board_key:
                return r['url'], r.get('fallback_url')
        # 없으면 첫 번째 활성 URL
        if rows:
            return rows[0]['url'], rows[0].get('fallback_url')
        return None
    except Exception:
        return None


def get_all_crawler_urls(crawler_id: str) -> List[dict]:
    """크롤러의 모든 활성 URL 반환 (다게시판 크롤러용)."""
    try:
        import db
        return db.get_crawler_urls(crawler_id=crawler_id, active_only=True)
    except Exception:
        return []


def record_link_check(crawler_id: str, url: str, ok: bool,
                       http_status: Optional[int] = None,
                       error: Optional[str] = None) -> None:
    """크롤 시 URL 접속 결과를 link_status DB에 기록.
    관리자 페이지 탭 ③에서 자동으로 실패 URL 확인 가능."""
    try:
        import db
        db.record_link_status(crawler_id, url, is_valid=ok,
                              http_status=http_status, error_msg=error)
    except Exception:
        pass


def execute_with_fallback(crawler_id: str, primary_fn, fallback_fn=None):
    """
    primary_fn 실행 → 실패 시 fallback_fn 실행.

    - primary_fn 결과가 빈 list거나 예외 → 실패로 판단
    - db.crawler_urls에 fallback_url 있으면 자동 시도
    - 결과 자동 link_status 기록
    """
    url_info = get_crawler_url(crawler_id)
    primary_url = url_info[0] if url_info else None
    fallback_url = url_info[1] if url_info else None

    try:
        items = primary_fn()
        if items:
            if primary_url:
                record_link_check(crawler_id, primary_url, True, 200)
            return items, "primary"
    except Exception as e:
        if primary_url:
            record_link_check(crawler_id, primary_url, False, None, str(e)[:200])

    # 폴백 시도
    if fallback_fn and fallback_url:
        try:
            items = fallback_fn()
            record_link_check(crawler_id, fallback_url, True, 200)
            return items, "fallback"
        except Exception as e:
            record_link_check(crawler_id, fallback_url, False, None, str(e)[:200])

    return [], "failed"


if __name__ == "__main__":
    # 자체 테스트
    print(f"기본 키워드 갯수: {len(DEFAULT_XLSX_KEYWORDS)}")
    kws = get_keywords()
    print(f"DB 로드 키워드: {len(kws)}개")
    print(f"첫 5개: {kws[:5]}")

    for cid in ['jbdc', 'jpdc', 'gmcc']:
        u = get_crawler_url(cid)
        print(f"{cid}: {u}")
