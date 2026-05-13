# -*- coding: utf-8 -*-
"""
크롤러 데이터 자동 검증
- 크롤러 직접 실행 결과와 DB 데이터 비교
- 데이터 정합성 검사 (필드 누락, 날짜 형식 등)
- 문제점을 리포트로 출력
"""
import db
import re
import sqlite3
from datetime import datetime, timedelta


def validate_crawler(crawler_id, info, days=30):
    """단일 크롤러 검증"""
    crawler = info["instance"]
    name = info["name"]

    issues = []

    # 1. DB에서 해당 크롤러 데이터 가져오기
    with db.get_conn() as conn:
        c = conn.cursor()
        rows = c.execute(
            "SELECT * FROM crawl_data WHERE crawler_id = ?",
            (crawler_id,)
        ).fetchall()
        db_count = len(rows)
        db_items = [dict(r) for r in rows]

    if db_count == 0:
        issues.append(f"DB에 데이터 없음")
        return {"id": crawler_id, "name": name, "db_count": 0, "issues": issues}

    # 2. 데이터 정합성
    no_title = sum(1 for i in db_items if not i.get("title"))
    no_date = sum(1 for i in db_items if not i.get("date"))
    no_url = sum(1 for i in db_items if not i.get("url"))
    no_org = sum(1 for i in db_items if not i.get("organization"))
    bad_date_format = sum(
        1 for i in db_items
        if i.get("date") and not re.match(r"\d{4}[-./]\d{2}[-./]\d{2}", str(i["date"]))
    )

    if no_title:
        issues.append(f"제목 누락 {no_title}건")
    if no_date:
        issues.append(f"날짜 누락 {no_date}건")
    if no_url:
        issues.append(f"URL 누락 {no_url}건")
    if no_org and no_org == db_count:
        issues.append(f"기관 정보 전부 누락 ({no_org}/{db_count})")
    if bad_date_format > db_count * 0.1:
        issues.append(f"날짜 형식 오류 {bad_date_format}건")

    # 3. 날짜 범위 확인
    dates = [str(i["date"])[:10] for i in db_items if i.get("date")]
    if dates:
        min_date = min(dates)
        max_date = max(dates)
        # 최근 30일 범위 확인
        cutoff = (datetime.now() - timedelta(days=days+5)).strftime("%Y-%m-%d")
        old_data = sum(1 for d in dates if d.replace(".", "-") < cutoff)
        if old_data > db_count * 0.3:
            issues.append(f"날짜 범위 벗어남 ({old_data}/{db_count}이 {days+5}일 전)")

    # 4. 중복 확인
    with db.get_conn() as conn:
        c = conn.cursor()
        dups = c.execute("""
            SELECT title, date, COUNT(*) as cnt
            FROM crawl_data
            WHERE crawler_id = ?
            GROUP BY title, date
            HAVING cnt > 1
        """, (crawler_id,)).fetchall()
        if dups:
            issues.append(f"중복 {len(dups)}쌍 존재")

    # 5. 크롤러 직접 호출해서 비교 (라이브 vs DB)
    # 수집 시점 확인 - 최근 1시간 이내 수집이면 차이 무시
    last_run_at = None
    with db.get_conn() as conn:
        c = conn.cursor()
        row = c.execute(
            "SELECT last_run_at FROM crawler_status WHERE crawler_id = ?",
            (crawler_id,)
        ).fetchone()
        if row:
            last_run_at = row["last_run_at"]

    skip_freshness = False
    if last_run_at:
        try:
            last_dt = datetime.fromisoformat(last_run_at)
            mins_ago = (datetime.now() - last_dt).total_seconds() / 60
            if mins_ago < 60:
                skip_freshness = True  # 수집 후 1시간 이내면 신선도 검증 스킵
        except Exception:
            pass

    if not skip_freshness:
        try:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
            live = crawler.search("", max_pages=2, start_date=start_date, end_date=end_date)
            if live:
                live_titles = {i.get("title", "").strip() for i in live[:5]}
                with db.get_conn() as conn:
                    c = conn.cursor()
                    db_titles = {
                        r["title"] for r in c.execute(
                            "SELECT title FROM crawl_data WHERE crawler_id = ? AND date >= ?",
                            (crawler_id, start_date)
                        ).fetchall()
                    }
                missing = live_titles - db_titles
                # 절반 이상 누락이면 문제
                if len(missing) >= len(live_titles) * 0.5:
                    issues.append(f"최근 게시물 {len(missing)}/{len(live_titles)}개 DB에 없음")
        except Exception as e:
            issues.append(f"라이브 비교 실패: {str(e)[:60]}")

    return {
        "id": crawler_id,
        "name": name,
        "db_count": db_count,
        "min_date": min(dates) if dates else None,
        "max_date": max(dates) if dates else None,
        "issues": issues,
    }


def validate_group(crawler_dict, days=30):
    """그룹 전체 검증"""
    print(f"\n{'='*70}")
    print(f"  검증 시작 ({len(crawler_dict)}개 크롤러)")
    print(f"{'='*70}\n")

    all_results = []
    perfect = 0
    has_issues = 0

    for cid, info in crawler_dict.items():
        result = validate_crawler(cid, info, days)
        all_results.append(result)

        if not result["issues"]:
            perfect += 1
            mark = "✅"
        else:
            has_issues += 1
            mark = "⚠️"

        date_range = ""
        if result.get("min_date"):
            date_range = f"  날짜 {result['min_date']}~{result['max_date']}"
        print(f"  {mark} {result['name']}: {result['db_count']}건{date_range}")
        for issue in result["issues"]:
            print(f"    ⚠️  {issue}")

    print(f"\n{'='*70}")
    print(f"  결과: ✅ {perfect}개  /  ⚠️ {has_issues}개")
    print(f"{'='*70}\n")

    return all_results


if __name__ == "__main__":
    import urllib3, sys
    urllib3.disable_warnings()
    print("크롤러 로딩...")
    exec(open("app.py").read().split("if __name__")[0])

    if len(sys.argv) > 1:
        group = sys.argv[1]
        cids = CRAWLER_GROUPS.get(group, [])
        if not cids:
            print(f"그룹 '{group}' 없음")
            sys.exit(1)
        crawler_dict = {cid: CRAWLERS[cid] for cid in cids}
    else:
        # DB에 있는 크롤러만
        with db.get_conn() as conn:
            c = conn.cursor()
            rows = c.execute("SELECT DISTINCT crawler_id FROM crawl_data").fetchall()
            cids = [r["crawler_id"] for r in rows]
        crawler_dict = {cid: CRAWLERS[cid] for cid in cids if cid in CRAWLERS}

    validate_group(crawler_dict)
