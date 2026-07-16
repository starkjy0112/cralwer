# -*- coding: utf-8 -*-
"""
알리오 전체 크롤 + 만료 항목 삭제 동기화 스크립트.
- 사이트 현재 데이터만 남기고 나머지는 DB에서 삭제
- 사이트 totalCnt와 우리 DB 카운트 일치 확인
"""
import sys, time
sys.path.insert(0, '.')
import urllib3; urllib3.disable_warnings()

from alio_crawler import AlioCrawler
import db

def main():
    t0 = time.time()
    print("=== 알리오 전체 크롤 시작 ===")
    c = AlioCrawler(concurrency=10)
    # 전체 (수천 페이지) 다 잡기
    items = c.search(start_date='2000-01-01', end_date='2099-12-31', max_pages=99999)
    print(f"\n크롤 완료: {len(items)}건 / {int(time.time()-t0)}초")

    if not items:
        print("결과 없음. 중단.")
        return

    # 신규 저장 (INSERT OR IGNORE)
    print("\n=== DB 신규 저장 ===")
    new = db.save_items('alio', '알리오', '수시공시', items)
    print(f"신규 +{new}건")

    # 크롤된 URL set 만들기
    fresh_urls = {it['url'] for it in items if it.get('url')}
    print(f"\n크롤된 유니크 URL: {len(fresh_urls)}건")

    # DB에서 fresh_urls에 없는 것 삭제 (동기화)
    print("\n=== 만료 항목 삭제 (fresh_urls에 없는 것) ===")
    with db.get_conn() as conn:
        # 기존 DB URL 목록
        rows = conn.execute('SELECT url FROM crawl_data WHERE crawler_id="alio"').fetchall()
        db_urls = {r[0] for r in rows}
        print(f'DB 기존: {len(db_urls)}건')
        # 삭제 대상
        to_delete = db_urls - fresh_urls
        print(f'삭제 대상 (사이트에 없음): {len(to_delete)}건')
        if to_delete:
            # 배치 삭제
            batch = 500
            deleted = 0
            urls_list = list(to_delete)
            for i in range(0, len(urls_list), batch):
                chunk = urls_list[i:i+batch]
                placeholders = ','.join('?' * len(chunk))
                cur = conn.execute(f'DELETE FROM crawl_data WHERE crawler_id="alio" AND url IN ({placeholders})', chunk)
                deleted += cur.rowcount
            conn.commit()
            print(f'삭제 완료: {deleted}건')

    # 최종 확인
    with db.get_conn() as conn:
        r = conn.execute('SELECT COUNT(*) FROM crawl_data WHERE crawler_id="alio"').fetchone()
        print(f'\n최종 DB: {r[0]}건')
    print(f'전체 소요: {int(time.time()-t0)}초')

if __name__ == "__main__":
    main()
