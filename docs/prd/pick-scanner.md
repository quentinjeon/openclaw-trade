# PRD: 백테스트 기반 종목 스캐너·자동매수

## 목적
- 시스템 트레이딩과 동일한 **조건식 백테스트 엔진**으로 다수 심볼을 스캔하고 **0~100 점수** 부여.
- **최저 점수 이상** + (옵션) **현재 봉 매수 조건 충족** 시 `RiskManager` → `ExecutionAgent`로 **자동 매수**.

## API
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/picks/config` | 설정 + 템플릿 목록 |
| PUT | `/api/picks/config` | 설정 저장 (`backend/data/pick_scanner_config.json`) |
| POST | `/api/picks/scan` | 수동 스캔 |
| POST | `/api/picks/auto-buy-once?force=` | 자동매수 1회 |

## 프론트
- `/picks` — 설정·스캔 테이블·자동매수 버튼

## 주의
- 점수는 과거 성과 기반이며 수익 보장 없음.
- 실거래 전 페이퍼로 검증 권장.

*2026-03-18*
