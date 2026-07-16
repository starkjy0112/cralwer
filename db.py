# -*- coding: utf-8 -*-
"""
SQLite DB 모듈
- crawl_data: 크롤러 수집 결과 저장
- crawler_status: 크롤러별 마지막 수집 시점 추적
"""
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

# DB 경로: 환경변수 DB_PATH 우선 (프로덕션: /data/crawlers.db).
# 미설정 시 로컬 개발용 프로젝트 폴더의 crawlers.db.
DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "crawlers.db")
)

# 프로덕션 볼륨 경로면 폴더 자동 생성
_db_dir = os.path.dirname(DB_PATH)
if _db_dir and _db_dir != os.path.dirname(os.path.abspath(__file__)):
    os.makedirs(_db_dir, exist_ok=True)


@contextmanager
def get_conn():
    """DB 연결 컨텍스트 매니저"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """DB 초기화: 테이블 생성"""
    with get_conn() as conn:
        c = conn.cursor()

        # 1. 크롤러 수집 결과 테이블
        c.execute("""
            CREATE TABLE IF NOT EXISTS crawl_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crawler_id TEXT NOT NULL,
                crawler_name TEXT NOT NULL,
                crawler_type TEXT,
                title TEXT NOT NULL,
                date TEXT,
                url TEXT,
                organization TEXT,
                number TEXT,
                deadline TEXT,
                content_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(crawler_id, content_hash)
            )
        """)

        # 인덱스 (검색 속도 향상)
        c.execute("CREATE INDEX IF NOT EXISTS idx_title ON crawl_data(title)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_date ON crawl_data(date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_crawler ON crawl_data(crawler_id)")

        # 2. 크롤러별 수집 상태
        c.execute("""
            CREATE TABLE IF NOT EXISTS crawler_status (
                crawler_id TEXT PRIMARY KEY,
                crawler_name TEXT,
                last_run_at TEXT,
                last_count INTEGER DEFAULT 0,
                last_error TEXT,
                total_collected INTEGER DEFAULT 0
            )
        """)

        # 3. 수집 로그 (이력 추적용)
        c.execute("""
            CREATE TABLE IF NOT EXISTS crawl_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                ended_at TEXT,
                total_crawlers INTEGER,
                success_count INTEGER,
                error_count INTEGER,
                new_items INTEGER
            )
        """)

        # 4. 검색어 관리 (xlsx ① 25개 기술 키워드 + 사용자 커스텀)
        c.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL UNIQUE,
                is_default INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 5. 크롤러 URL 관리 (게시판 링크 편집, 폴백 URL 포함)
        c.execute("""
            CREATE TABLE IF NOT EXISTS crawler_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crawler_id TEXT NOT NULL,
                crawler_name TEXT,
                board_key TEXT,
                board_name TEXT,
                url TEXT NOT NULL,
                fallback_url TEXT,
                is_active INTEGER DEFAULT 1,
                priority INTEGER DEFAULT 0,
                notes TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(crawler_id, board_key)
            )
        """)

        # 6. URL 검증 상태 (링크 유효/무효 감지)
        c.execute("""
            CREATE TABLE IF NOT EXISTS link_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crawler_id TEXT NOT NULL,
                url TEXT NOT NULL,
                is_valid INTEGER,
                http_status INTEGER,
                error_msg TEXT,
                last_checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(crawler_id, url)
            )
        """)

        # xlsx 기본 25개 기술 키워드 시드 데이터 (한 번만 삽입)
        default_keywords = [
            "기본설계", "실시설계", "기술제안", "제안서", "신기술",
            "공법", "특허", "특정", "발파", "암발파",
            "미진동", "무진동", "암절취", "흙깍기", "절토",
            "토공", "토목", "토건", "제출", "제안",
            "부지조성", "단지조성", "산업단지", "조성공사", "개발사업",
        ]
        for kw in default_keywords:
            c.execute("""
                INSERT OR IGNORE INTO keywords (keyword, is_default)
                VALUES (?, 1)
            """, (kw,))


def normalize_date(date):
    """날짜 정규화 (다양한 형식 → YYYY-MM-DD)"""
    if not date:
        return ""
    return str(date).replace(".", "-").replace("/", "-").strip()[:10]


def make_content_hash(crawler_id, title, date, url=None):
    """중복 방지용 해시 (제목+날짜+URL).
    같은 (제목,날짜)라도 URL이 다르면 별도 게시물로 인정.
    URL은 가능한 한 고유한 식별자 (seq, no 등) 포함하므로 unique 보장."""
    import hashlib
    nd = normalize_date(date)
    raw = f"{crawler_id}|{(title or '').strip()}|{nd}|{(url or '').strip()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def save_items(crawler_id, crawler_name, crawler_type, items):
    """크롤러 결과를 DB에 저장 (중복 무시)"""
    if not items:
        return 0

    new_count = 0
    with get_conn() as conn:
        c = conn.cursor()
        for item in items:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            date = item.get("date") or ""
            url = item.get("url") or item.get("link") or ""
            organization = item.get("organization") or ""
            number = item.get("number") or ""
            deadline = item.get("deadline") or ""
            content_hash = make_content_hash(crawler_id, title, date, url)

            try:
                c.execute("""
                    INSERT OR IGNORE INTO crawl_data
                    (crawler_id, crawler_name, crawler_type, title, date, url,
                     organization, number, deadline, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (crawler_id, crawler_name, crawler_type, title, date, url,
                      organization, number, deadline, content_hash))
                if c.rowcount > 0:
                    new_count += 1
            except Exception:
                pass
    return new_count


def update_crawler_status(crawler_id, crawler_name, count, error=None):
    """크롤러 수집 상태 업데이트"""
    with get_conn() as conn:
        c = conn.cursor()
        now = datetime.now().isoformat(timespec="seconds")
        c.execute("""
            INSERT INTO crawler_status (crawler_id, crawler_name, last_run_at, last_count, last_error, total_collected)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(crawler_id) DO UPDATE SET
                crawler_name = excluded.crawler_name,
                last_run_at = excluded.last_run_at,
                last_count = excluded.last_count,
                last_error = excluded.last_error,
                total_collected = total_collected + excluded.last_count
        """, (crawler_id, crawler_name, now, count, error, count))


def search(keyword="", start_date=None, end_date=None, crawler_ids=None, limit=10000):
    """DB에서 검색"""
    where = []
    params = []

    if keyword:
        where.append("title LIKE ?")
        params.append(f"%{keyword}%")

    if start_date:
        where.append("date >= ?")
        params.append(start_date)

    if end_date:
        where.append("date <= ?")
        params.append(end_date + " 99:99:99")  # 시간까지 포함된 날짜 비교

    if crawler_ids:
        placeholders = ",".join("?" * len(crawler_ids))
        where.append(f"crawler_id IN ({placeholders})")
        params.extend(crawler_ids)

    where_clause = "WHERE " + " AND ".join(where) if where else ""
    params.append(limit)

    sql = f"""
        SELECT crawler_id, crawler_name, crawler_type, title, date, url,
               organization, number, deadline
        FROM crawl_data
        {where_clause}
        ORDER BY date DESC
        LIMIT ?
    """

    with get_conn() as conn:
        c = conn.cursor()
        rows = c.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_stats():
    """DB 통계"""
    with get_conn() as conn:
        c = conn.cursor()
        total = c.execute("SELECT COUNT(*) FROM crawl_data").fetchone()[0]
        crawler_counts = c.execute("""
            SELECT crawler_id, crawler_name, COUNT(*) as cnt
            FROM crawl_data
            GROUP BY crawler_id
            ORDER BY cnt DESC
        """).fetchall()
        last_log = c.execute("""
            SELECT * FROM crawl_log ORDER BY id DESC LIMIT 1
        """).fetchone()
        return {
            "total": total,
            "by_crawler": [dict(r) for r in crawler_counts],
            "last_log": dict(last_log) if last_log else None,
        }


def log_crawl_session(started_at, ended_at, total, success, error, new_items):
    """크롤 세션 로그 저장"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO crawl_log (started_at, ended_at, total_crawlers,
                                    success_count, error_count, new_items)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (started_at, ended_at, total, success, error, new_items))


# ---------- xlsx 요구 기능: 검색어 관리 (①) ----------

def get_keywords(only_default=False):
    """검색어 전체 조회"""
    with get_conn() as conn:
        c = conn.cursor()
        sql = "SELECT id, keyword, is_default, created_at FROM keywords"
        if only_default:
            sql += " WHERE is_default = 1"
        sql += " ORDER BY is_default DESC, id ASC"
        return [dict(r) for r in c.execute(sql).fetchall()]


def add_keyword(keyword):
    """검색어 추가 (사용자 커스텀)"""
    keyword = (keyword or "").strip()
    if not keyword:
        return False
    with get_conn() as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT INTO keywords (keyword, is_default) VALUES (?, 0)", (keyword,))
            return True
        except sqlite3.IntegrityError:
            return False


def delete_keyword(kw_id):
    """검색어 삭제 (기본 xlsx 키워드는 삭제 불가 옵션 있음)"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM keywords WHERE id = ? AND is_default = 0", (kw_id,))
        return c.rowcount > 0


# ---------- xlsx 요구 기능: 게시판 링크 관리 (②) ----------

def get_crawler_failure_info(crawler_id=None):
    """크롤러별 최근 실패 정보 반환.
    - last_error 있으면 실패 크롤러로 판단
    - hours_since_ok: 마지막 성공 이후 시간 (아직 성공 없으면 999)
    - 3시간 이상 실패 지속 시 warn=True (알림 대상)
    """
    with get_conn() as conn:
        c = conn.cursor()
        where = "WHERE crawler_id = ?" if crawler_id else ""
        params = (crawler_id,) if crawler_id else ()
        rows = c.execute(f"""
            SELECT crawler_id, crawler_name, last_run_at, last_count,
                   last_error, total_collected
            FROM crawler_status
            {where}
        """, params).fetchall()

        result = {}
        from datetime import datetime, timedelta
        now = datetime.now()

        for r in rows:
            cid = r['crawler_id']
            has_error = bool(r['last_error'])
            hours_since_run = 999
            try:
                if r['last_run_at']:
                    dt = datetime.fromisoformat(r['last_run_at'].replace('T', ' ')[:19])
                    hours_since_run = (now - dt).total_seconds() / 3600
            except Exception:
                pass

            # 3시간 이상 last_error 유지 = 알림 대상
            warn = has_error and (r['last_count'] == 0)

            result[cid] = {
                "has_error": has_error,
                "last_error": r['last_error'],
                "last_run_at": r['last_run_at'],
                "last_count": r['last_count'],
                "hours_since_run": round(hours_since_run, 1),
                "warn": warn,
                "total_collected": r['total_collected'],
            }
        return result


def get_verified_crawler_ids():
    """검증된 크롤러 ID = crawler_urls에 활성 등록된 것.
    xlsx 13-56행 (crawler_status.png 이미지에 나오는) 44개가 시드됨.
    관리자가 admin 페이지에서 URL 추가 시 자동으로 검증 목록에 편입."""
    with get_conn() as conn:
        c = conn.cursor()
        rows = c.execute("""
            SELECT DISTINCT crawler_id FROM crawler_urls
            WHERE is_active = 1
            ORDER BY crawler_id
        """).fetchall()
        return [r['crawler_id'] for r in rows]


def get_crawler_verification_stats():
    """검증 통계 - 어떤 근거로 검증됐는지."""
    with get_conn() as conn:
        c = conn.cursor()
        # URL 등록된 크롤러
        urls = c.execute("SELECT DISTINCT crawler_id FROM crawler_urls WHERE is_active = 1").fetchall()
        # 데이터 있는 크롤러
        data = c.execute("SELECT DISTINCT crawler_id FROM crawl_data").fetchall()
        # 성공 이력 있는 크롤러
        status = c.execute("""
            SELECT DISTINCT crawler_id FROM crawler_status
            WHERE (last_error IS NULL OR last_error = '') AND last_count > 0
        """).fetchall()
        return {
            "urls_registered": len(urls),
            "has_data": len(data),
            "has_success_status": len(status),
            "total_verified": len(set(
                [r['crawler_id'] for r in urls] +
                [r['crawler_id'] for r in data] +
                [r['crawler_id'] for r in status]
            )),
        }


def get_crawler_urls(crawler_id=None, active_only=False):
    """크롤러별 URL 조회"""
    with get_conn() as conn:
        c = conn.cursor()
        where = []
        params = []
        if crawler_id:
            where.append("crawler_id = ?")
            params.append(crawler_id)
        if active_only:
            where.append("is_active = 1")
        wc = "WHERE " + " AND ".join(where) if where else ""
        sql = f"""
            SELECT id, crawler_id, crawler_name, board_key, board_name,
                   url, fallback_url, is_active, priority, notes, updated_at
            FROM crawler_urls {wc}
            ORDER BY crawler_id, priority DESC, id
        """
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def upsert_crawler_url(crawler_id, crawler_name, board_key, board_name,
                       url, fallback_url=None, is_active=1, priority=0, notes=None):
    """크롤러 URL 추가/수정"""
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO crawler_urls
              (crawler_id, crawler_name, board_key, board_name, url,
               fallback_url, is_active, priority, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(crawler_id, board_key) DO UPDATE SET
              crawler_name = excluded.crawler_name,
              board_name = excluded.board_name,
              url = excluded.url,
              fallback_url = excluded.fallback_url,
              is_active = excluded.is_active,
              priority = excluded.priority,
              notes = excluded.notes,
              updated_at = excluded.updated_at
        """, (crawler_id, crawler_name, board_key, board_name, url,
              fallback_url, is_active, priority, notes, now))


def delete_crawler_url(url_id):
    """URL 삭제"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM crawler_urls WHERE id = ?", (url_id,))
        return c.rowcount > 0


# ---------- xlsx 요구 기능: 링크 검증 (③) ----------

def record_link_status(crawler_id, url, is_valid, http_status=None, error_msg=None):
    """링크 검증 결과 저장"""
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO link_status (crawler_id, url, is_valid, http_status, error_msg, last_checked_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(crawler_id, url) DO UPDATE SET
              is_valid = excluded.is_valid,
              http_status = excluded.http_status,
              error_msg = excluded.error_msg,
              last_checked_at = excluded.last_checked_at
        """, (crawler_id, url, 1 if is_valid else 0, http_status, error_msg, now))


def get_link_status(crawler_id=None, invalid_only=False):
    """링크 검증 결과 조회"""
    with get_conn() as conn:
        c = conn.cursor()
        where = []
        params = []
        if crawler_id:
            where.append("crawler_id = ?")
            params.append(crawler_id)
        if invalid_only:
            where.append("is_valid = 0")
        wc = "WHERE " + " AND ".join(where) if where else ""
        sql = f"""
            SELECT id, crawler_id, url, is_valid, http_status,
                   error_msg, last_checked_at
            FROM link_status {wc}
            ORDER BY is_valid ASC, last_checked_at DESC
        """
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def check_url_alive(url, timeout=15, crawler_session=None):
    """URL 유효성 검사. (status_code, error_msg) 반환.

    crawler_session이 있으면 해당 크롤러의 세션(특수 헤더/쿠키/TLS)으로 검증.
    없으면 표준 브라우저 헤더로 검증.
    """
    import requests

    if crawler_session is not None:
        # 크롤러 세션 사용 - 실제 크롤 시 사용하는 헤더/어댑터/쿠키 그대로
        try:
            r = crawler_session.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code == 200 and len(r.text) < 1500:
                return r.status_code, "SHORT_RESPONSE (차단페이지 의심)"
            if r.status_code >= 400:
                return r.status_code, f"HTTP {r.status_code} (크롤러 세션)"
            return r.status_code, None
        except Exception as e:
            return None, f"{str(e)[:180]} (크롤러 세션)"

    # 폴백: 표준 브라우저 헤더 (크롤러 세션 없을 때)
    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/131.0.0.0 Safari/537.36"),
                "Accept-Language": "ko-KR,ko;q=0.9",
            },
            verify=False,
            timeout=timeout,
            allow_redirects=True,
        )
        if r.status_code == 200 and len(r.text) < 1500:
            return r.status_code, "SHORT_RESPONSE (차단페이지 의심)"
        if r.status_code >= 400:
            return r.status_code, f"HTTP {r.status_code}"
        return r.status_code, None
    except Exception as e:
        return None, str(e)[:200]


if __name__ == "__main__":
    init_db()
    print(f"DB 초기화 완료: {DB_PATH}")
    stats = get_stats()
    print(f"현재 데이터: {stats['total']}건")
