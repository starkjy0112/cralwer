#!/usr/bin/env python3
"""크롤러 그룹별 검증 스크립트
사용법: python3 verify_group.py [그룹명]
예시:  python3 verify_group.py 공공기관
       python3 verify_group.py 서울
       python3 verify_group.py all  (전체)
"""
import sys
import time
import importlib
import urllib3
import concurrent.futures

urllib3.disable_warnings()

# app.py에서 CRAWLERS, CRAWLER_GROUPS, GROUP_ORDER 로드
_app_code = open("app.py").read().split('if __name__')[0]
exec(_app_code)

def verify_crawler(cid, info):
    """개별 크롤러 검증"""
    name = info["name"]
    result = {
        "id": cid,
        "name": name,
        "status": "?",
        "gongo": 0,
        "yongyek": 0,
        "search_ok": False,
        "date_ok": False,
        "link_ok": False,
        "error": None,
    }

    try:
        crawler = info["instance"]
        t0 = time.time()

        # _fetch_page가 있으면 총건수 기반 비교 (빠름)
        has_fetch = hasattr(crawler, "_fetch_page")

        if has_fetch:
            items1, total1 = crawler._fetch_page("공고", 1)
            items2, total2 = crawler._fetch_page("용역", 1)
            gongo_count = total1
            yongyek_count = total2
            items = items1 if items1 else items2
        else:
            # _fetch_page 없는 크롤러 (나라장터 등 함수 기반)
            r1 = crawler.search("공고", max_pages=1)
            r2 = crawler.search("용역", max_pages=1)
            gongo_count = len(r1)
            yongyek_count = len(r2)
            items = r1 if r1 else r2

        elapsed = time.time() - t0

        result["gongo"] = gongo_count
        result["yongyek"] = yongyek_count
        result["elapsed"] = round(elapsed, 1)

        # 3. 검색 작동 여부
        if gongo_count == 0 and yongyek_count == 0:
            result["search_ok"] = False
            result["status"] = "0건"
        elif gongo_count != yongyek_count:
            result["search_ok"] = True
        else:
            # 건수가 같으면 제목으로 비교
            titles1 = set(i.get("title", "") for i in (items1 if has_fetch else r1))
            titles2 = set(i.get("title", "") for i in (items2 if has_fetch else r2))
            if titles1 != titles2:
                result["search_ok"] = True  # 내용이 다르면 검색 작동
            else:
                result["search_ok"] = False  # 제목까지 같으면 검색 미작동

        # 4. 날짜 파싱 확인
        if items:
            dates = [i.get("date", "") for i in items[:5]]
            has_date = sum(1 for d in dates if d and len(d) >= 8)
            result["date_ok"] = has_date >= len(dates) * 0.5

        # 5. 링크 유효성
        if items:
            links = [i.get("url") or i.get("link") for i in items[:3]]
            has_link = sum(1 for l in links if l and l.startswith("http"))
            result["link_ok"] = has_link > 0

        # 종합 상태
        if gongo_count == 0 and yongyek_count == 0:
            result["status"] = "0건"
        elif not result["search_ok"]:
            result["status"] = "검색X"
        elif not result["date_ok"]:
            result["status"] = "날짜X"
        elif not result["link_ok"]:
            result["status"] = "링크X"
        else:
            result["status"] = "OK"

    except Exception as e:
        result["status"] = "에러"
        result["error"] = str(e)[:60]
        result["elapsed"] = 0

    return result


def verify_group(group_name):
    """그룹 검증 실행"""
    if group_name == "all":
        cids = []
        for g in GROUP_ORDER:
            cids.extend(CRAWLER_GROUPS.get(g, []))
    elif group_name in CRAWLER_GROUPS:
        cids = CRAWLER_GROUPS[group_name]
    else:
        print(f"그룹 '{group_name}' 없음. 가능한 그룹:")
        for g in GROUP_ORDER:
            if g in CRAWLER_GROUPS:
                print(f"  {g} ({len(CRAWLER_GROUPS[g])}개)")
        return

    print(f"\n{'='*70}")
    print(f"  [{group_name}] 검증 시작 - {len(cids)}개 크롤러")
    print(f"{'='*70}\n")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for cid in cids:
            info = CRAWLERS[cid]
            futures[executor.submit(verify_crawler, cid, info)] = cid

        for future in concurrent.futures.as_completed(futures):
            r = future.result()
            results.append(r)
            # 실시간 출력
            icon = {"OK": "✅", "검색X": "⚠️", "날짜X": "📅", "링크X": "🔗", "0건": "❌", "에러": "💥"}.get(r["status"], "?")
            search_mark = "O" if r["search_ok"] else "X"
            date_mark = "O" if r["date_ok"] else "X"
            link_mark = "O" if r["link_ok"] else "X"
            err = f" ({r['error']})" if r["error"] else ""
            print(f"  {icon} {r['name']:<25} 공고={r['gongo']:<5} 용역={r['yongyek']:<5} 검색={search_mark} 날짜={date_mark} 링크={link_mark} {r.get('elapsed',0):.1f}s{err}")

    # 요약
    ok = sum(1 for r in results if r["status"] == "OK")
    search_fail = sum(1 for r in results if r["status"] == "검색X")
    zero = sum(1 for r in results if r["status"] == "0건")
    date_fail = sum(1 for r in results if r["status"] == "날짜X")
    link_fail = sum(1 for r in results if r["status"] == "링크X")
    errors = sum(1 for r in results if r["status"] == "에러")

    print(f"\n{'='*70}")
    print(f"  [{group_name}] 결과 요약")
    print(f"{'='*70}")
    print(f"  ✅ 정상:     {ok}개")
    print(f"  ⚠️  검색X:    {search_fail}개")
    print(f"  ❌ 0건:      {zero}개")
    print(f"  📅 날짜X:    {date_fail}개")
    print(f"  🔗 링크X:    {link_fail}개")
    print(f"  💥 에러:     {errors}개")
    print(f"  합계:        {len(results)}개")
    print(f"{'='*70}\n")

    # 문제 크롤러 목록
    problems = [r for r in results if r["status"] != "OK"]
    if problems:
        print("  [문제 크롤러 상세]")
        for r in sorted(problems, key=lambda x: x["status"]):
            err = f" - {r['error']}" if r["error"] else ""
            print(f"    {r['status']:<5} {r['id']}: {r['name']} (공고={r['gongo']}, 용역={r['yongyek']}){err}")


if __name__ == "__main__":
    group = sys.argv[1] if len(sys.argv) > 1 else None
    if not group:
        print("사용법: python3 verify_group.py [그룹명]")
        print("가능한 그룹:")
        for g in GROUP_ORDER:
            if g in CRAWLER_GROUPS:
                print(f"  {g} ({len(CRAWLER_GROUPS[g])}개)")
        print("  all (전체)")
    else:
        verify_group(group)
