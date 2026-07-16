# -*- coding: utf-8 -*-
"""
백그라운드 크롤러 수집 함수
- 모든 크롤러를 주기적으로 실행해 DB에 저장
- APScheduler가 1시간마다 호출
"""
import concurrent.futures
import time
from datetime import datetime, timedelta
import db


# 큰 사이트 (수만 건/30일) - 깊이 수집
LARGE_SITES = {
    "nara",         # 나라장터
    "alio",         # 알리오 입찰
    "alio_item",    # 알리오 물자
    "seoul_cis",    # 서울 계약마당
    "gh",           # 경기주택도시공사
}

# 중간 사이트
MEDIUM_SITES = {
    "lh", "kr",
    "gangwon", "chungnam", "chungbuk", "gb_gosi", "gb_notice",
    "gsnd_gosi", "gsnd_notice", "jeonnam_bid", "jeonnam_notice",
    "busan_gosi", "busan_notice", "incheon", "gwangju", "daejeon_gosi",
}


def get_max_pages(crawler_id):
    """크롤러별 max_pages 결정"""
    # 알리오는 30일치가 약 2만건 → 2,000페이지 (early stop 동작)
    if crawler_id in ("alio", "alio_item"):
        return 3000
    if crawler_id in LARGE_SITES:
        return 200    # 약 2000~2만건
    if crawler_id in MEDIUM_SITES:
        return 50     # 약 500~5000건
    return 20         # 일반 시군청 약 200건


def collect_one(crawler_id, info, days=30):
    """단일 크롤러 실행.
    통합: crawler_config로 링크 상태 자동 기록 + 크롤 실패 시 폴백 URL 안내.
    """
    from crawler_config import get_crawler_url, record_link_check

    crawler = info["instance"]
    name = info["name"]
    ctype = info.get("type", "")

    # DB에 등록된 URL 정보
    url_info = get_crawler_url(crawler_id)
    primary_url = url_info[0] if url_info else None
    fallback_url = url_info[1] if url_info else None

    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        max_pages = get_max_pages(crawler_id)

        items = crawler.search(
            "",
            max_pages=max_pages,
            start_date=start_date,
            end_date=end_date,
        )

        new_count = db.save_items(crawler_id, name, ctype, items)
        db.update_crawler_status(crawler_id, name, len(items))
        # 크롤 성공 → 링크 정상
        if primary_url:
            record_link_check(crawler_id, primary_url, ok=True, http_status=200)
        return crawler_id, name, len(items), new_count, None

    except Exception as e:
        err = str(e)[:200]
        db.update_crawler_status(crawler_id, name, 0, error=err)
        # 크롤 실패 → 링크 상태 기록 (관리자 페이지 탭 ③에서 자동 표시됨)
        if primary_url:
            record_link_check(crawler_id, primary_url, ok=False, error=err)
        # 폴백 URL 있으면 로그에 알림
        if fallback_url:
            err = f"{err} [폴백가능: {fallback_url}]"
        return crawler_id, name, 0, 0, err


def collect_all(crawlers, days=30, max_workers=10, verbose=True):
    """전체 크롤러 수집 (DB에 저장)"""
    started_at = datetime.now().isoformat(timespec="seconds")
    started_ts = time.time()

    if verbose:
        print(f"\n{'='*60}")
        print(f"  [수집 시작] {started_at}")
        print(f"  크롤러: {len(crawlers)}개  /  범위: 최근 {days}일")
        print(f"{'='*60}\n")

    success = 0
    error = 0
    new_total = 0
    fetched_total = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(collect_one, cid, info, days): cid
            for cid, info in crawlers.items()
        }

        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            try:
                cid, name, count, new_count, err = future.result(timeout=120)
                if err:
                    error += 1
                    if verbose:
                        print(f"  [{i}/{len(crawlers)}] ❌ {name}: {err[:50]}")
                else:
                    success += 1
                    new_total += new_count
                    fetched_total += count
                    if verbose and (i % 20 == 0 or new_count > 0):
                        print(f"  [{i}/{len(crawlers)}] ✅ {name}: 수집={count} 신규={new_count}")
            except concurrent.futures.TimeoutError:
                error += 1
                cid = futures[future]
                if verbose:
                    print(f"  [{i}/{len(crawlers)}] ⏱️ {cid}: timeout")

    ended_at = datetime.now().isoformat(timespec="seconds")
    elapsed = time.time() - started_ts

    db.log_crawl_session(started_at, ended_at, len(crawlers), success, error, new_total)

    if verbose:
        print(f"\n{'='*60}")
        print(f"  [수집 완료] {ended_at}  ({elapsed:.0f}초)")
        print(f"  성공: {success}개  /  에러: {error}개")
        print(f"  수집: {fetched_total}건  /  신규: {new_total}건")
        print(f"{'='*60}\n")

    return {
        "success": success,
        "error": error,
        "fetched": fetched_total,
        "new": new_total,
        "elapsed": elapsed,
    }


if __name__ == "__main__":
    """단독 실행 (테스트용): python3 collector.py"""
    import sys
    db.init_db()

    # app.py에서 CRAWLERS 가져오기
    print("크롤러 로딩 중...")
    exec(open("app.py").read().split("if __name__")[0])

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    result = collect_all(CRAWLERS, days=days)
    print(f"\n최종: 신규 {result['new']}건 저장됨")
