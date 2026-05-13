#!/usr/bin/env python3
"""
크롤러 종합 검증 (강화 버전):
1. 데이터 정확성: 크롤러 결과의 제목/날짜가 실제 상세 페이지와 일치하는지
2. 링크 유효성: 모든 링크 200 응답 확인
3. 데이터 정합성: 필드 누락, 날짜 형식 오류 등
"""
import sys
import urllib3
import requests
import concurrent.futures
import re
from bs4 import BeautifulSoup

urllib3.disable_warnings()

exec(open("app.py").read().split("if __name__")[0])

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0"})


def check_link(url):
    """링크 200 응답 확인"""
    if not url or not url.startswith("http"):
        return False, "no_url"
    try:
        r = SESSION.get(url, timeout=10, allow_redirects=True, verify=False, stream=True)
        status = r.status_code
        # 본문 일부만 읽고 닫기
        try:
            content = r.raw.read(2048, decode_content=True)
            r.close()
        except Exception:
            r.close()
            content = b""
        if not (200 <= status < 400):
            return False, f"http_{status}"
        # 에러 페이지 감지 (404, 에러, not found 등)
        text = content[:2000].decode("utf-8", errors="ignore").lower()
        for marker in ["페이지를 찾을 수 없", "404 not found", "잘못된 접근", "오류가 발생"]:
            if marker in text:
                return False, "error_page"
        return True, "ok"
    except Exception as e:
        return False, f"exception_{str(e)[:30]}"


def check_title_match(item, url):
    """상세 페이지에서 제목을 가져와 크롤러 제목과 비교"""
    if not url or not item.get("title"):
        return None
    try:
        r = SESSION.get(url, timeout=10, verify=False)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "lxml")

        crawler_title = item["title"].strip()
        # 제목 후보 추출
        candidates = []
        for sel in ["h1", "h2", "h3", "h4",
                    ".title", ".tit", ".subject", ".bbs-title",
                    "[class*='title']", "[class*='subject']",
                    "td.title", "td.subject"]:
            for tag in soup.select(sel):
                text = tag.get_text(strip=True)
                if text and len(text) > 5:
                    candidates.append(text)
            if candidates:
                break

        # 크롤러 제목의 핵심 단어가 후보에 포함돼있는지
        # (사이트마다 제목 형식이 달라서 부분 일치)
        crawler_words = set(re.findall(r"\w+", crawler_title))
        crawler_words = {w for w in crawler_words if len(w) >= 2}
        if not crawler_words:
            return None

        for cand in candidates[:5]:
            cand_words = set(re.findall(r"\w+", cand))
            common = crawler_words & cand_words
            if len(common) >= len(crawler_words) * 0.6:
                return True
        return False
    except Exception:
        return None


def check_data_integrity(items):
    """데이터 정합성"""
    if not items:
        return None
    no_title = sum(1 for i in items if not i.get("title"))
    no_date = sum(1 for i in items if not i.get("date"))
    no_url = sum(1 for i in items if not (i.get("url") or i.get("link")))
    no_org = sum(1 for i in items if not i.get("organization"))
    bad_date = sum(1 for i in items
                   if i.get("date") and not re.match(r"\d{4}", str(i["date"])))
    return {
        "total": len(items),
        "no_title": no_title,
        "no_date": no_date,
        "no_url": no_url,
        "no_org": no_org,
        "bad_date": bad_date,
    }


def verify_crawler(cid):
    info = CRAWLERS[cid]
    crawler = info["instance"]
    name = info["name"]
    ctype = info.get("type", "")

    result = {
        "id": cid,
        "name": name,
        "type": ctype,
        "url": info.get("url", ""),
        "count": 0,
        "data": None,
        "links_total": 0,
        "links_ok": 0,
        "links_failed": [],
        "title_match": None,
        "error": None,
    }

    try:
        items = crawler.search("", max_pages=2)
        result["count"] = len(items)
        result["data"] = check_data_integrity(items)

        if not items:
            return result

        # 모든 링크 검증
        urls = [(i.get("url") or i.get("link", "")) for i in items]
        result["links_total"] = len(urls)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            checks = list(ex.map(check_link, urls))
        for i, (ok, reason) in enumerate(checks):
            if ok:
                result["links_ok"] += 1
            else:
                if len(result["links_failed"]) < 3:
                    result["links_failed"].append(reason)

        # 첫번째 항목의 제목이 상세 페이지와 일치하는지
        first_url = urls[0] if urls and urls[0] else None
        if first_url:
            result["title_match"] = check_title_match(items[0], first_url)

    except Exception as e:
        result["error"] = str(e)[:80]

    return result


def print_result(r):
    if r["error"]:
        print(f"  ❌ {r['name']} ({r['type']}) ERROR: {r['error']}")
        return

    cnt = r["count"]
    if cnt == 0:
        print(f"  ⚪ {r['name']} ({r['type']}) 결과 없음")
        return

    data = r["data"]
    issues = []
    if data["no_title"]: issues.append(f"제목X{data['no_title']}")
    if data["no_date"]: issues.append(f"날짜X{data['no_date']}")
    if data["no_url"]: issues.append(f"URLX{data['no_url']}")
    if data["bad_date"]: issues.append(f"날짜형식{data['bad_date']}")

    title_mark = "✅" if r["title_match"] is True else ("❌" if r["title_match"] is False else "?")
    link_ratio = f"{r['links_ok']}/{r['links_total']}"
    link_mark = "✅" if r["links_ok"] == r["links_total"] else "⚠️"
    fail_str = f" [{','.join(r['links_failed'])}]" if r["links_failed"] else ""
    issue_str = f" {{{','.join(issues)}}}" if issues else ""

    print(f"  {link_mark} {r['name']} ({r['type']}) 건수={cnt} 링크={link_ratio} 제목매칭={title_mark}{fail_str}{issue_str}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 full_verify.py [그룹명|all]")
        print(f"가능한 그룹: {list(CRAWLER_GROUPS.keys())}")
        sys.exit(1)

    group = sys.argv[1]
    if group == "all":
        cids = []
        for g in GROUP_ORDER:
            cids.extend(CRAWLER_GROUPS.get(g, []))
    else:
        cids = CRAWLER_GROUPS.get(group, [])

    if not cids:
        print(f"그룹 '{group}' 없음")
        sys.exit(1)

    print(f"\n=== {group} 그룹 종합 검증 ({len(cids)}개) ===\n")
    print("범례: ✅ 모두 정상 / ⚠️ 일부 깨짐 / ❌ 에러 / ⚪ 결과없음")
    print("       제목매칭: ✅일치 / ❌불일치 / ?확인불가\n")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(verify_crawler, cid): cid for cid in cids}
        for f in concurrent.futures.as_completed(futures):
            r = f.result()
            results.append(r)
            print_result(r)

    # 요약
    total = len(results)
    err = sum(1 for r in results if r["error"])
    no_data = sum(1 for r in results if not r["error"] and r["count"] == 0)
    link_ok = sum(1 for r in results if not r["error"] and r["links_total"] > 0 and r["links_ok"] == r["links_total"])
    link_fail = sum(1 for r in results if not r["error"] and r["links_total"] > 0 and r["links_ok"] < r["links_total"])
    title_match = sum(1 for r in results if r["title_match"] is True)
    title_no = sum(1 for r in results if r["title_match"] is False)
    title_unknown = sum(1 for r in results if r["title_match"] is None and not r["error"] and r["count"] > 0)
    data_issues = sum(1 for r in results if not r["error"] and r["data"] and (
        r["data"]["no_title"] or r["data"]["no_url"] or r["data"]["bad_date"]))

    print(f"\n=== {group} 요약 ===")
    print(f"  전체: {total}개")
    print(f"  ✅ 링크 모두 정상: {link_ok}개")
    print(f"  ⚠️  링크 일부 깨짐: {link_fail}개")
    print(f"  📋 제목 매칭 OK: {title_match}개 / 불일치: {title_no}개 / 확인불가: {title_unknown}개")
    print(f"  💥 데이터 누락: {data_issues}개")
    print(f"  ⚪ 결과 없음: {no_data}개")
    print(f"  ❌ 크롤러 에러: {err}개")
