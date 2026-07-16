# -*- coding: utf-8 -*-
"""
자동 크롤러 검증 도구
- 크롤러 새로 실행해서 사이트의 최신 데이터 가져옴
- 우리 DB의 같은 기간 데이터와 비교
- 누락/차이 리포트 출력

사용법:
    python3 auto_verify.py             # 모든 그룹 검증
    python3 auto_verify.py 공공기관     # 특정 그룹만
    python3 auto_verify.py 서울 경기   # 여러 그룹
"""
import sys
import time
import urllib3
import concurrent.futures
from datetime import datetime, timedelta

urllib3.disable_warnings()

import db

# app.py에서 CRAWLERS 로드
exec(open("app.py").read().split("if __name__")[0])


def verify_crawler(crawler_id, info, days=7):
    """
    단일 크롤러 검증
    - 크롤러 실행 → 사이트의 최신 데이터
    - DB의 같은 기간 데이터
    - 비교
    """
    name = info["name"]
    crawler = info["instance"]

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    result = {
        "id": crawler_id,
        "name": name,
        "site_count": 0,
        "db_count": 0,
        "site_titles": set(),
        "db_titles": set(),
        "error": None,
    }

    # 1) 크롤러 직접 실행 (사이트에서 최신 데이터)
    try:
        live_items = crawler.search(
            "", max_pages=20, start_date=start_date, end_date=end_date
        )
        result["site_count"] = len(live_items)
        result["site_titles"] = {i.get("title", "").strip() for i in live_items if i.get("title")}
    except Exception as e:
        result["error"] = f"크롤러 실패: {str(e)[:80]}"
        return result

    # 2) DB에서 같은 기간 데이터
    try:
        with db.get_conn() as conn:
            c = conn.cursor()
            rows = c.execute("""
                SELECT title FROM crawl_data
                WHERE crawler_id = ?
                AND ((date >= ? AND date <= ?)
                     OR (date >= ? AND date <= ?))
            """, (
                crawler_id,
                start_date, end_date + " 99:99:99",
                start_date.replace("-", "."), end_date.replace("-", ".") + " 99:99:99"
            )).fetchall()
            result["db_count"] = len(rows)
            result["db_titles"] = {r["title"].strip() for r in rows if r["title"]}
    except Exception as e:
        result["error"] = f"DB 조회 실패: {str(e)[:80]}"

    return result


def grade(result):
    """결과 등급 매기기"""
    if result["error"]:
        return "ERROR", "❌"

    site_n = len(result["site_titles"])
    db_n = len(result["db_titles"])

    if site_n == 0 and db_n == 0:
        return "EMPTY", "⚪"  # 양쪽 다 비어있음 (정상)

    if site_n == 0:
        return "DB_ONLY", "⚠️"  # 사이트는 비어있는데 DB만 있음 (이상)

    matched = result["site_titles"] & result["db_titles"]
    coverage = len(matched) / site_n * 100

    if coverage >= 95:
        return "OK", "✅"
    elif coverage >= 80:
        return "WARN", "⚠️"
    else:
        return "BAD", "❌"


def print_result(result):
    """단일 결과 출력"""
    g, icon = grade(result)

    if result["error"]:
        print(f"  {icon} {result['name']} ERROR: {result['error']}")
        return

    site_n = len(result["site_titles"])
    db_n = len(result["db_titles"])

    if site_n == 0 and db_n == 0:
        print(f"  {icon} {result['name']}: 양쪽 데이터 없음 (최근 7일 비어있음)")
        return

    matched = result["site_titles"] & result["db_titles"]
    only_site = result["site_titles"] - result["db_titles"]
    only_db = result["db_titles"] - result["site_titles"]

    coverage = len(matched) / site_n * 100 if site_n > 0 else 0

    print(f"  {icon} {result['name']:<25} 사이트={site_n:<4} DB={db_n:<4} 매칭={len(matched):<4} ({coverage:.0f}%)")

    if only_site and g != "OK":
        sample = list(only_site)[:2]
        print(f"      ↳ DB 누락: {sample[0][:50]}{'...' if len(sample) > 1 else ''}")


def verify_group(group_name, days=7):
    """그룹 검증"""
    cids = CRAWLER_GROUPS.get(group_name, [])
    if not cids:
        print(f"\n그룹 '{group_name}' 없음")
        return []

    print(f"\n{'='*70}")
    print(f"  [{group_name}] {len(cids)}개 크롤러 자동 검증 (최근 {days}일)")
    print(f"{'='*70}")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(verify_crawler, cid, CRAWLERS[cid], days): cid
            for cid in cids if cid in CRAWLERS
        }
        for future in concurrent.futures.as_completed(futures):
            r = future.result()
            results.append(r)

    # 정렬 후 출력
    results.sort(key=lambda x: x["name"])
    for r in results:
        print_result(r)

    # 요약
    grades = [grade(r)[0] for r in results]
    print(f"\n  ✅ 정상: {grades.count('OK')}개")
    print(f"  ⚠️  경고: {grades.count('WARN')}개")
    print(f"  ❌ 문제: {grades.count('BAD')}개")
    print(f"  ❌ 에러: {grades.count('ERROR')}개")
    print(f"  ⚪ 빈데이터: {grades.count('EMPTY')}개")

    return results


def main():
    # 인자: 그룹 이름들 (없으면 전체)
    if len(sys.argv) > 1:
        groups_to_verify = sys.argv[1:]
    else:
        groups_to_verify = [g for g in GROUP_ORDER if g in CRAWLER_GROUPS]

    all_results = []
    t0 = time.time()

    for g in groups_to_verify:
        results = verify_group(g)
        all_results.extend(results)

    elapsed = time.time() - t0

    # 전체 요약
    grades = [grade(r)[0] for r in all_results]
    print(f"\n{'='*70}")
    print(f"  🏁 전체 결과 ({elapsed:.0f}초)")
    print(f"{'='*70}")
    print(f"  전체: {len(all_results)}개")
    print(f"  ✅ 정상 (95%+): {grades.count('OK')}개")
    print(f"  ⚠️  경고 (80~95%): {grades.count('WARN')}개")
    print(f"  ❌ 문제 (80% 미만): {grades.count('BAD')}개")
    print(f"  ❌ 에러: {grades.count('ERROR')}개")
    print(f"  ⚪ 빈데이터 (검증 불가): {grades.count('EMPTY')}개")

    # 문제 크롤러 목록
    problems = [r for r in all_results if grade(r)[0] in ("BAD", "ERROR")]
    if problems:
        print(f"\n  📋 수정 필요 ({len(problems)}개):")
        for r in problems:
            g, icon = grade(r)
            print(f"    {icon} {r['name']}: {r.get('error') or '낮은 매칭률'}")


if __name__ == "__main__":
    main()
