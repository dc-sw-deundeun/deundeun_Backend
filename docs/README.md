# deundeun Backend Docs

팀원이 공통으로 봐야 하는 문서만 이 디렉터리에서 Git으로 관리합니다.

| 문서 | 목적 |
|------|------|
| [implementation-status.md](./implementation-status.md) | 현재 구현된 API와 아직 stub인 영역 |
| [api-home.md](./api-home.md) | 홈 aggregation과 오늘의 미션 조회 API 가이드 |
| [api-record-ocr.md](./api-record-ocr.md) | 검진 업로드·OCR 플로우 상세 API 가이드 |
| [api-health-metric-analysis.md](./api-health-metric-analysis.md) | 건강 지표 분석 저장·조회 플로우 상세 API 가이드 |
| [api-character-growth.md](./api-character-growth.md) | 캐릭터 성장·동물 해금 API 가이드 |
| [development-environment.md](./development-environment.md) | 로컬 개발, 테스트, CI 기준 환경 |
| [deployment-onprem.md](./deployment-onprem.md) | 온프레미스 스테이징 서버와 CD 설정 |
| [architecture.md](./architecture.md) | 백엔드 레이어, 도메인, 외부 연동 구조 |

## 문서 관리 기준

- 실행 중인 API 계약은 Swagger/OpenAPI가 우선입니다.
- 코드 구현 현황은 [implementation-status.md](./implementation-status.md)를 기준으로 갱신합니다.
- 서버 secret이 들어간 `.env`, `.env.server`, `/opt/deundeun/.env`는 문서나 커밋에 포함하지 않습니다.
- Phase별 작업 메모, 요구사항 원본, 긴 설계 초안은 로컬 참고 자료로 두고 Git 공유 대상에서 제외합니다.

## 빠른 링크

| 항목 | 링크 |
|------|------|
| 로컬 Swagger | http://localhost:8000/docs |
| 스테이징 Swagger | http://api.deundeun.xyz/docs |
| Health check | `GET /health` |
| API prefix | `/api/v1` |
