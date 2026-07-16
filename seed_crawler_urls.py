# -*- coding: utf-8 -*-
"""xlsx 13-56행 44개 크롤러 URL을 DB에 seed.
이미지(crawler_status.png)에 표시되는 검증 완료 크롤러 44개.
"""
import openpyxl
import db
from gen_status_image import ROWS  # 44개 매핑 (row_num, crawler_id, name, policy)


def seed():
    db.init_db()

    wb = openpyxl.load_workbook("서칭기관 목록(250311)_중복삭제.xlsx", data_only=True)
    ws = wb.active

    added = 0
    skipped = 0
    for row_num, cid, name, policy in ROWS:
        # xlsx 실제 URL 가져오기
        path = (ws.cell(row_num, 4).value or "").strip()
        url = (ws.cell(row_num, 5).value or "").strip()

        if not url:
            print(f"  ⚠ 행 {row_num} {cid}: URL 없음, skip")
            skipped += 1
            continue

        # 게시판 키 결정 (경로에서 마지막 부분)
        board_key = "default"
        board_name = path.split(">")[-1].strip() if ">" in path else path

        db.upsert_crawler_url(
            crawler_id=cid,
            crawler_name=name,
            board_key=board_key,
            board_name=board_name or "게시판",
            url=url,
            fallback_url=None,
            is_active=1,
            priority=10,
            notes=f"xlsx {row_num}행 지정 URL",
        )
        added += 1

    print(f"\n등록: {added}개, skip: {skipped}개")

    urls = db.get_crawler_urls()
    print(f"DB 총 URL: {len(urls)}")

    # 검증 통계
    verified = db.get_verified_crawler_ids()
    print(f"검증된 크롤러: {len(verified)}개")


if __name__ == "__main__":
    seed()
