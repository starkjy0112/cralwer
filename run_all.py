# -*- coding: utf-8 -*-
"""
모든 그룹 자동 수집 + 검증
- 작은 그룹부터 순차 진행
- 각 그룹별 결과를 메모리/리포트로 저장
"""
import urllib3
import time
from datetime import datetime
import db
import collector
import validator

urllib3.disable_warnings()


def run_group(group_name, crawlers, days=30):
    """단일 그룹 수집 + 검증"""
    print(f"\n{'='*70}")
    print(f"  ▶ {group_name} ({len(crawlers)}개)")
    print(f"{'='*70}")

    t0 = time.time()
    result = collector.collect_all(crawlers, days=days, max_workers=8, verbose=False)
    elapsed = time.time() - t0

    print(f"  수집: {elapsed:.0f}초, 성공 {result['success']}/{len(crawlers)}, "
          f"에러 {result['error']}, 신규 {result['new']}건")

    return {
        "group": group_name,
        "crawlers": len(crawlers),
        "elapsed": elapsed,
        "success": result["success"],
        "error": result["error"],
        "fetched": result["fetched"],
        "new": result["new"],
    }


if __name__ == "__main__":
    print("크롤러 로딩...")
    exec(open("app.py").read().split("if __name__")[0])

    # 남은 그룹들 (이미 한 거 제외): 충북 ✅, 공공기관 ✅
    GROUPS = [
        "인천", "부산", "대구", "광주", "대전", "울산", "세종", "제주",
        "광역도청",
        "전북", "충남", "경남",
        "전남", "강원", "서울",
        "경북",
        "경기",
    ]

    summary = []
    overall_t0 = time.time()

    for g in GROUPS:
        cids = CRAWLER_GROUPS.get(g, [])
        if not cids:
            continue
        crawler_dict = {cid: CRAWLERS[cid] for cid in cids}
        r = run_group(g, crawler_dict)
        summary.append(r)

    overall_elapsed = time.time() - overall_t0

    print(f"\n{'='*70}")
    print(f"  ★ 전체 결과 ({overall_elapsed:.0f}초)")
    print(f"{'='*70}")
    for r in summary:
        print(f"  {r['group']:<12} {r['crawlers']:>3}개  "
              f"성공 {r['success']:>3}  에러 {r['error']:>2}  "
              f"신규 {r['new']:>5}건  ({r['elapsed']:.0f}초)")

    total_new = sum(r["new"] for r in summary)
    total_err = sum(r["error"] for r in summary)
    print(f"\n  총 신규: {total_new}건  /  에러: {total_err}개")

    # DB 통계
    stats = db.get_stats()
    print(f"\n  DB 총 데이터: {stats['total']}건")
