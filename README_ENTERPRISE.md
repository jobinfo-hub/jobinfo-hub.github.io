# 커리어픽 대기업 채용 — 1차 설치 안내

## 설치
1. 기존 저장소의 `index.html`과 `prep.html`을 백업하세요.
2. ZIP의 파일과 폴더 구조를 유지해 GitHub 저장소 루트에 업로드하세요. `.github/workflows/enterprise_jobs.yml`은 반드시 해당 경로여야 합니다.
3. `https://jobinfo-hub.github.io/enterprise.html`에서 **현재 게시된 공고가 없습니다** 안내가 보이면 승인 대기 모드가 정상입니다.
4. GitHub Actions에서 `대기업 채용 자동 수집 (승인 후 활성화)`를 수동 실행해 보세요. API 승인 전에는 `enterprise_jobs.json`이 비어 있는 상태로 유지됩니다.

## 승인 후
1. 사람인 승인 안내의 **재게시·상업적 이용·출처 표기 조건**을 먼저 확인합니다.
2. GitHub → Settings → Secrets and variables → Actions → Secrets에 `SARAMIN_API_KEY`를 등록합니다. 키는 HTML이나 채팅에 올리지 마세요.
3. 같은 메뉴의 Variables에 `ENTERPRISE_COLLECTION_ENABLED` = `true`를 설정합니다.
4. Actions에서 수동 실행해 `enterprise_status.json`과 `enterprise_jobs.json` 결과를 검증합니다.
5. **주의**: 사람인 API 실제 응답 필드·페이지 처리·제공 데이터 범위는 승인 후 문서와 대조해 검증해야 합니다. 현재 수집기는 단일 페이지 100건의 초기 어댑터이며, 전체 공고 수집을 보장하지 않습니다. API 허용 조건에 맞춰 추가 개선이 필요합니다.

## 설계 원칙
- 기존 블로그·공기업 수집 workflow와 데이터는 수정하지 않습니다.
- 승인 전 가짜 공고를 게시하지 않습니다.
- API 오류/빈 응답은 기존 정상 데이터를 덮어쓰지 않습니다.
- 최초 발견 시각을 유지하고 API 제공 공고 원문으로 연결합니다.
- 수집 주기: 매시 17분(UTC 기준), GitHub Actions 지연 가능.
- GitHub Pages 배포가 `.github` 및 `scripts` 업로드와 무관한지 저장소 설정을 확인하세요.
