"""
내 지갑 API 라우터
GET /api/wallet/balance  - Binance 계좌 잔액 조회 (페이퍼/실거래 모두 지원)

자산 계산 순서:
  1. fetch_balance() → 코인별 보유 수량
  2. USDT: 가격 1.0 고정
  3. 기타 코인: fetch_ticker("{CURRENCY}/USDT") → 현재가
  4. usd_value = amount × current_price
  5. krw_value = usd_value × fx_rate (market 라우터 캐시 재사용)
  6. pct_of_total = (usd_value / total_usd) × 100
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from loguru import logger

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────

class WalletAsset(BaseModel):
    currency: str           # "BTC", "USDT", "ETH"
    amount: float           # 보유 수량
    usd_value: float        # USD 환산 가치
    krw_value: float        # KRW 환산 가치
    pct_of_total: float     # 전체 대비 비중 (%)
    current_price_usd: float  # 현재 단가 (USD)
    change_24h_pct: float   # 24시간 변동률 (%)


class WalletBalanceResponse(BaseModel):
    total_usd: float        # 전체 자산 USD
    total_krw: float        # 전체 자산 KRW
    cash_usd: float         # USDT 잔고 (현금)
    coin_value_usd: float   # 코인 총 가치 (USDT 제외)
    asset_count: int        # 보유 자산 종류 수
    mode: str               # "paper" | "live"
    fx_rate: float          # USD/KRW 환율
    updated_at: str         # 업데이트 시각 (ISO)
    assets: List[WalletAsset]


# ──────────────────────────────────────────────
# 엔드포인트
# ──────────────────────────────────────────────

# 소액 필터 기준 (USD)
_DUST_THRESHOLD_USD = 0.0001


@router.get("/balance", response_model=WalletBalanceResponse)
async def get_wallet_balance():
    """
    Binance 계좌 잔액 조회

    - 페이퍼트레이딩: ExchangeConnector._paper_balance 에서 직접 읽음
    - 실거래: fetch_balance() 호출 후 코인별 현재가 환산
    - 환율: /api/market/fx 캐시 재사용 (별도 HTTP 호출 없음)
    """
    from main import exchange
    from routers.market import _fx_cache, get_fx_rate

    if exchange is None or not exchange.is_connected:
        raise HTTPException(status_code=503, detail="거래소 연결이 초기화되지 않았습니다.")

    # 1. 환율 조회 (캐시 우선)
    try:
        fx = await get_fx_rate()
        fx_rate = fx.usd_krw
    except Exception as e:
        logger.warning(f"환율 조회 실패, 기본값 1450 사용: {e}")
        fx_rate = 1450.0

    # 2. 잔고 조회
    try:
        raw_balance = await exchange.fetch_balance()
    except Exception as e:
        logger.error(f"잔고 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"잔고 조회 실패: {str(e)}")

    # 3. 코인별 보유 수량 추출 (total 기준, 0 초과만)
    holdings: dict[str, float] = {}

    # 페이퍼트레이딩: _paper_balance 직접 접근
    if exchange.paper_trading:
        for currency, amount in exchange._paper_balance.items():
            if amount > 0:
                holdings[currency] = amount
    else:
        total = raw_balance.get("total", {})
        for currency, amount in total.items():
            if amount and float(amount) > 0:
                holdings[currency] = float(amount)

    # 4. 각 자산 USD 가치 계산
    assets: List[WalletAsset] = []
    total_usd = 0.0
    cash_usd = 0.0

    for currency, amount in holdings.items():
        try:
            if currency in ("USDT", "BUSD", "USDC", "DAI", "TUSD"):
                # 스테이블코인은 1.0 고정
                current_price = 1.0
                change_24h = 0.0
            else:
                # 코인 현재가 조회
                ticker = await exchange.fetch_ticker(f"{currency}/USDT")
                current_price = float(ticker.get("last", 0) or 0)
                change_24h = float(ticker.get("percentage", 0) or 0)

            usd_value = amount * current_price

            # 소액 필터 (0.0001 USD 미만 제외)
            if usd_value < _DUST_THRESHOLD_USD:
                continue

            assets.append(WalletAsset(
                currency=currency,
                amount=amount,
                usd_value=round(usd_value, 4),
                krw_value=0.0,  # 아래에서 total 확정 후 계산
                pct_of_total=0.0,  # 아래에서 계산
                current_price_usd=round(current_price, 8),
                change_24h_pct=round(change_24h, 2),
            ))
            total_usd += usd_value

            if currency in ("USDT", "BUSD", "USDC", "DAI", "TUSD"):
                cash_usd += usd_value

        except Exception as e:
            logger.warning(f"자산 가격 조회 실패 ({currency}): {e}")
            # 조회 실패 자산은 목록에서 제외

    # 5. 비중 및 KRW 계산
    for asset in assets:
        asset.pct_of_total = round((asset.usd_value / total_usd * 100) if total_usd > 0 else 0.0, 2)
        asset.krw_value = round(asset.usd_value * fx_rate, 0)

    # 6. 금액 내림차순 정렬
    assets.sort(key=lambda a: a.usd_value, reverse=True)

    coin_value_usd = total_usd - cash_usd
    mode = "paper" if exchange.paper_trading else "live"

    logger.info(f"지갑 조회 완료: 총 ${total_usd:,.2f} ({len(assets)}개 자산, {mode} 모드)")

    return WalletBalanceResponse(
        total_usd=round(total_usd, 2),
        total_krw=round(total_usd * fx_rate, 0),
        cash_usd=round(cash_usd, 2),
        coin_value_usd=round(coin_value_usd, 4),
        asset_count=len(assets),
        mode=mode,
        fx_rate=fx_rate,
        updated_at=datetime.utcnow().isoformat(),
        assets=assets,
    )
