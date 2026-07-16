# Fly.io / Docker 배포용
FROM python:3.11-slim

# Playwright 브라우저 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 먼저 (캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Chromium
RUN playwright install chromium && playwright install-deps chromium

# 앱 소스
COPY . .

# 볼륨 마운트 경로 (Fly.io에서 /data 자동 마운트)
# DB_PATH 환경변수는 fly.toml에서 /data/crawlers.db로 설정됨
RUN mkdir -p /data

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:5001/health || exit 1

EXPOSE 5001

# gunicorn: 워커 2, 스레드 4, 타임아웃 120초 (긴 크롤 대응)
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--threads", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
