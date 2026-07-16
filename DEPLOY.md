# Fly.io 배포 가이드

## 1. Fly CLI 설치 (한 번만)

```bash
# macOS
brew install flyctl

# 또는
curl -L https://fly.io/install.sh | sh
```

## 2. Fly.io 계정 만들기

```bash
fly auth signup    # 신규
# 또는
fly auth login     # 기존
```

무료 계정 만들 때 **신용카드 등록 필요** (사용량 초과 시 결제, 이 프로젝트는 무료 티어 내).

## 3. 첫 배포 (프로젝트 폴더에서)

```bash
cd /Users/teramime/Documents/project_16

# 앱 생성 + 볼륨 생성 + 배포
fly launch --name bid-crawler-dashboard --region nrt --no-deploy

# 영속 볼륨 생성 (SQLite DB 저장용)
fly volumes create crawler_data --region nrt --size 3

# 환경변수 설정 (시크릿)
fly secrets set ADMIN_TOKEN=$(openssl rand -base64 32)
fly secrets set NARA_API_KEY=dda419df735cfb226cff2561e3fd9eca16b0eda9730135bdbbca9a30510aa1d8

# 배포
fly deploy
```

## 4. ADMIN_TOKEN 확인

```bash
fly secrets list
# 값은 볼 수 없음. 재설정하려면:
fly secrets set ADMIN_TOKEN=<새토큰>
```

토큰 값 알려면 설정 시 별도 저장.

## 5. 기존 DB 마이그레이션 (선택)

로컬의 `crawlers.db` (178만건)를 볼륨에 업로드:

```bash
# SFTP로 볼륨 접근
fly ssh sftp shell
> put crawlers.db /data/crawlers.db
> exit

# 앱 재시작
fly apps restart bid-crawler-dashboard
```

**주의**: `fly deploy` 시 컨테이너 이미지에 로컬 DB 파일이 포함되면 볼륨 위에 안 씀. `.dockerignore`가 이걸 방지.

## 6. 배포 확인

```bash
# 앱 URL
fly open

# 관리자 페이지 (토큰 필요)
open "https://bid-crawler-dashboard.fly.dev/admin?token=<ADMIN_TOKEN>"

# 로그 실시간
fly logs

# 상태
fly status
```

## 7. 재배포 (코드 수정 후)

```bash
git add -A
git commit -m "..."
git push  # GitHub에도

fly deploy  # Fly.io 배포
```

---

## 무료 티어 한계

| 항목 | 무료 | 우리 사용 예상 |
|---|---|---|
| VM (shared-cpu-1x) | 3개 무료 | 1개 사용 |
| 메모리 | 256MB × 3 | 512MB 1개 (약간 초과 가능) |
| 볼륨 | 3GB 무료 | 2GB 예상 |
| 대역폭 | 100GB/월 | 여유 |

**초과 시 요금 청구**: 
- 추가 VM: ~$2/월
- 추가 볼륨: ~$0.15/GB/월

이 프로젝트는 대부분 무료 티어 내에서 동작.

---

## 트러블슈팅

### 배포 실패 (메모리 초과)
`fly.toml`에서 memory를 256mb → 512mb로 조정 (무료 초과 없음)

### 스케줄러 안 돌아감
```bash
fly logs | grep Scheduler
# "등록: 전체 1시간 + 알리오 30분" 로그 확인
```

### DB 손실 (볼륨 미마운트)
```bash
fly volumes list
# crawler_data 볼륨이 앱에 attached인지 확인
```

### 재배포 시 데이터 초기화 방지
`.dockerignore`에 `crawlers.db` 포함되어 있는지 확인.

---

## 요약: 명령어 3개

```bash
brew install flyctl
fly auth login
fly launch --name bid-crawler-dashboard --region nrt
fly volumes create crawler_data --region nrt --size 3
fly secrets set ADMIN_TOKEN=$(openssl rand -base64 32)
fly deploy
```
