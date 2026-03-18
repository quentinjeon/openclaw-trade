"""
시스템 트레이딩 API 라우터
조건식 CRUD, Text-to-Rule, 백테스트, 현재 조건 체크

GET    /api/system/conditions                조건식 목록
POST   /api/system/conditions                조건식 생성
GET    /api/system/conditions/{id}           조건식 단건
PUT    /api/system/conditions/{id}           조건식 수정
DELETE /api/system/conditions/{id}           조건식 삭제
POST   /api/system/text-to-rule              자연어 → 조건 변환
GET    /api/system/templates                 전략 템플릿 목록
POST   /api/system/backtest                  백테스트 실행
POST   /api/system/check-now                 현재 조건 체크
"""
import json
from datetime import datetime
from typing import List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from loguru import logger

from core.database import AsyncSessionLocal
from models.system_condition import SystemCondition
from services.rule_parser import parse_text_to_conditions, STRATEGY_TEMPLATES
from services.backtester import run_backtest
from services.condition_evaluator import evaluate_condition_group, get_current_indicator_values

router = APIRouter(prefix="/api/system", tags=["system-trading"])


# ──────────────────────────────────────────────
# DB 세션 의존성
# ──────────────────────────────────────────────

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ──────────────────────────────────────────────
# 요청/응답 스키마
# ──────────────────────────────────────────────

class ConditionGroupSchema(BaseModel):
    logic: str = "AND"          # "AND" | "OR"
    conditions: List[dict] = []


class ConditionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    buy_conditions: Optional[ConditionGroupSchema] = None
    sell_conditions: Optional[ConditionGroupSchema] = None
    is_active: bool = False


class ConditionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    buy_conditions: Optional[ConditionGroupSchema] = None
    sell_conditions: Optional[ConditionGroupSchema] = None
    is_active: Optional[bool] = None


class ConditionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    symbol: str
    timeframe: str
    buy_conditions: Optional[dict]
    sell_conditions: Optional[dict]
    is_active: bool
    created_at: str
    updated_at: str
    backtest_win_rate: Optional[float]
    backtest_total_trades: Optional[int]
    backtest_avg_return: Optional[float]
    backtest_max_drawdown: Optional[float]
    backtest_ran_at: Optional[str] = None


class TextToRuleRequest(BaseModel):
    text: str
    side: str = "buy"           # "buy" | "sell"


class TextToRuleResponse(BaseModel):
    success: bool
    group: Optional[dict]
    explanation: str
    method: str                 # "pattern" | "llm" | "failed"


class BacktestRequest(BaseModel):
    condition_id: Optional[int] = None
    buy_conditions: Optional[ConditionGroupSchema] = None
    sell_conditions: Optional[ConditionGroupSchema] = None
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    limit: int = 300            # 캔들 수 (최대 1000)


class CheckNowRequest(BaseModel):
    condition_id: Optional[int] = None
    buy_conditions: Optional[ConditionGroupSchema] = None
    sell_conditions: Optional[ConditionGroupSchema] = None
    symbol: str = "BTC/USDT"


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def _condition_to_response(c: SystemCondition) -> ConditionResponse:
    return ConditionResponse(
        id=c.id,
        name=c.name,
        description=c.description,
        symbol=c.symbol,
        timeframe=c.timeframe,
        buy_conditions=json.loads(c.buy_conditions) if c.buy_conditions else None,
        sell_conditions=json.loads(c.sell_conditions) if c.sell_conditions else None,
        is_active=c.is_active,
        created_at=c.created_at.isoformat(),
        updated_at=c.updated_at.isoformat(),
        backtest_win_rate=c.backtest_win_rate,
        backtest_total_trades=c.backtest_total_trades,
        backtest_avg_return=c.backtest_avg_return,
        backtest_max_drawdown=c.backtest_max_drawdown,
        backtest_ran_at=c.backtest_ran_at.isoformat() if c.backtest_ran_at else None,
    )


async def _fetch_candles_df(symbol: str, timeframe: str, limit: int):
    """거래소에서 캔들 데이터를 가져와 DataFrame으로 변환"""
    from main import exchange
    import pandas as pd

    if exchange is None or not exchange.is_connected:
        raise HTTPException(status_code=503, detail="거래소 연결이 초기화되지 않았습니다.")

    limit = min(limit, 1000)
    raw = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = (df["time"] / 1000).astype(int)  # ms → 초
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df


# ──────────────────────────────────────────────
# 조건식 CRUD
# ──────────────────────────────────────────────

@router.get("/conditions", response_model=List[ConditionResponse])
async def list_conditions(db: AsyncSession = Depends(get_db)):
    """조건식 전체 목록 조회"""
    result = await db.execute(select(SystemCondition).order_by(SystemCondition.updated_at.desc()))
    conditions = result.scalars().all()
    return [_condition_to_response(c) for c in conditions]


@router.post("/conditions", response_model=ConditionResponse)
async def create_condition(body: ConditionCreate, db: AsyncSession = Depends(get_db)):
    """새 조건식 생성"""
    cond = SystemCondition(
        name=body.name,
        description=body.description,
        symbol=body.symbol,
        timeframe=body.timeframe,
        buy_conditions=json.dumps(body.buy_conditions.dict()) if body.buy_conditions else None,
        sell_conditions=json.dumps(body.sell_conditions.dict()) if body.sell_conditions else None,
        is_active=body.is_active,
    )
    db.add(cond)
    await db.commit()
    await db.refresh(cond)
    logger.info(f"조건식 생성: id={cond.id} name='{cond.name}'")
    return _condition_to_response(cond)


@router.get("/conditions/{condition_id}", response_model=ConditionResponse)
async def get_condition(condition_id: int, db: AsyncSession = Depends(get_db)):
    """조건식 단건 조회"""
    cond = await db.get(SystemCondition, condition_id)
    if not cond:
        raise HTTPException(status_code=404, detail="조건식을 찾을 수 없습니다.")
    return _condition_to_response(cond)


@router.put("/conditions/{condition_id}", response_model=ConditionResponse)
async def update_condition(
    condition_id: int,
    body: ConditionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """조건식 수정"""
    cond = await db.get(SystemCondition, condition_id)
    if not cond:
        raise HTTPException(status_code=404, detail="조건식을 찾을 수 없습니다.")

    if body.name is not None:
        cond.name = body.name
    if body.description is not None:
        cond.description = body.description
    if body.symbol is not None:
        cond.symbol = body.symbol
    if body.timeframe is not None:
        cond.timeframe = body.timeframe
    if body.buy_conditions is not None:
        cond.buy_conditions = json.dumps(body.buy_conditions.dict())
    if body.sell_conditions is not None:
        cond.sell_conditions = json.dumps(body.sell_conditions.dict())
    if body.is_active is not None:
        cond.is_active = body.is_active

    cond.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(cond)
    return _condition_to_response(cond)


@router.delete("/conditions/{condition_id}")
async def delete_condition(condition_id: int, db: AsyncSession = Depends(get_db)):
    """조건식 삭제"""
    cond = await db.get(SystemCondition, condition_id)
    if not cond:
        raise HTTPException(status_code=404, detail="조건식을 찾을 수 없습니다.")
    await db.delete(cond)
    await db.commit()
    return {"message": f"조건식 {condition_id}이 삭제되었습니다."}


# ──────────────────────────────────────────────
# Text-to-Rule
# ──────────────────────────────────────────────

@router.post("/text-to-rule", response_model=TextToRuleResponse)
async def text_to_rule(body: TextToRuleRequest):
    """
    자연어 텍스트를 조건식 JSON으로 변환

    예: "RSI 30 이하이고 거래량 평균의 1.5배" → ConditionGroup
    """
    result = parse_text_to_conditions(body.text)
    return TextToRuleResponse(
        success=result["success"],
        group=result.get("group"),
        explanation=result.get("explanation", ""),
        method=result.get("method", "failed"),
    )


# ──────────────────────────────────────────────
# 전략 템플릿
# ──────────────────────────────────────────────

@router.get("/templates")
async def get_templates():
    """
    기본 제공 전략 템플릿 목록

    RSI 역추세, MACD 골든크로스, 볼린저 반등, 이평선 돌파, 스토캐스틱
    """
    templates = []
    for key, tmpl in STRATEGY_TEMPLATES.items():
        templates.append({
            "key": key,
            "name": tmpl["name"],
            "description": tmpl["description"],
            "buy_group": tmpl["buy_group"],
            "sell_group": tmpl["sell_group"],
        })
    return {"templates": templates}


# ──────────────────────────────────────────────
# 백테스트
# ──────────────────────────────────────────────

@router.post("/backtest")
async def backtest(body: BacktestRequest, db: AsyncSession = Depends(get_db)):
    """
    조건식 백테스트 실행

    - condition_id 또는 buy_conditions/sell_conditions 직접 전달
    - 결과: 신호 목록 + 통계 (승률, 평균수익, MDD 등)
    """
    # 조건 가져오기
    if body.condition_id is not None:
        cond = await db.get(SystemCondition, body.condition_id)
        if not cond:
            raise HTTPException(status_code=404, detail="조건식을 찾을 수 없습니다.")
        buy_group = json.loads(cond.buy_conditions) if cond.buy_conditions else {"logic": "AND", "conditions": []}
        sell_group = json.loads(cond.sell_conditions) if cond.sell_conditions else {"logic": "OR", "conditions": []}
        symbol = body.symbol or cond.symbol
        timeframe = body.timeframe or cond.timeframe
    else:
        if not body.buy_conditions or not body.sell_conditions:
            raise HTTPException(status_code=400, detail="condition_id 또는 buy_conditions/sell_conditions를 제공해주세요.")
        buy_group = body.buy_conditions.dict()
        sell_group = body.sell_conditions.dict()
        symbol = body.symbol
        timeframe = body.timeframe

    if not buy_group.get("conditions"):
        raise HTTPException(status_code=400, detail="매수 조건이 비어있습니다.")
    if not sell_group.get("conditions"):
        raise HTTPException(status_code=400, detail="매도 조건이 비어있습니다.")

    try:
        # 캔들 데이터 조회
        df = await _fetch_candles_df(symbol, timeframe, body.limit)

        # 백테스트 실행
        result = run_backtest(df, buy_group, sell_group)

        # 조건식에 결과 캐시 저장
        if body.condition_id is not None:
            cond_db = await db.get(SystemCondition, body.condition_id)
            if cond_db:
                stats = result["stats"]
                cond_db.backtest_win_rate = stats["win_rate"]
                cond_db.backtest_total_trades = stats["total_trades"]
                cond_db.backtest_avg_return = stats["avg_return_pct"]
                cond_db.backtest_max_drawdown = stats["max_drawdown_pct"]
                cond_db.backtest_ran_at = datetime.utcnow()
                await db.commit()

        logger.info(
            f"백테스트 완료: {symbol} {timeframe} | "
            f"신호={len(result['signals'])}건 | "
            f"승률={result['stats']['win_rate']}%"
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"백테스트 오류: {e}")
        raise HTTPException(status_code=500, detail=f"백테스트 실행 실패: {str(e)}")


# ──────────────────────────────────────────────
# 현재 조건 체크
# ──────────────────────────────────────────────

@router.post("/check-now")
async def check_now(body: CheckNowRequest, db: AsyncSession = Depends(get_db)):
    """
    현재 시장 데이터에 대해 조건식 즉시 평가

    Returns:
        triggered: 조건 발동 여부
        side: "BUY" | "SELL" | "HOLD"
        current_values: 각 지표의 현재 값
    """
    if body.condition_id is not None:
        cond = await db.get(SystemCondition, body.condition_id)
        if not cond:
            raise HTTPException(status_code=404, detail="조건식을 찾을 수 없습니다.")
        buy_group = json.loads(cond.buy_conditions) if cond.buy_conditions else {"logic": "AND", "conditions": []}
        sell_group = json.loads(cond.sell_conditions) if cond.sell_conditions else {"logic": "OR", "conditions": []}
        symbol = body.symbol or cond.symbol
    else:
        if not body.buy_conditions or not body.sell_conditions:
            raise HTTPException(status_code=400, detail="condition_id 또는 조건을 제공해주세요.")
        buy_group = body.buy_conditions.dict()
        sell_group = body.sell_conditions.dict()
        symbol = body.symbol

    try:
        # 최근 200봉 조회 (지표 계산에 충분한 데이터)
        df = await _fetch_candles_df(symbol, "1h", 200)

        buy_result = evaluate_condition_group(df, buy_group)
        sell_result = evaluate_condition_group(df, sell_group)

        buy_triggered = bool(buy_result.iloc[-1])
        sell_triggered = bool(sell_result.iloc[-1])

        if buy_triggered:
            side = "BUY"
        elif sell_triggered:
            side = "SELL"
        else:
            side = "HOLD"

        # 현재 지표 값
        all_conditions = buy_group.get("conditions", []) + sell_group.get("conditions", [])
        current_values = get_current_indicator_values(df, all_conditions)

        # 트리거된 조건 분류
        passed_buy = []
        failed_buy = []
        for c in buy_group.get("conditions", []):
            from services.condition_evaluator import _evaluate_single_condition
            res = _evaluate_single_condition(df, c)
            desc = f"{c.get('indicator_a', '')} {c.get('operator', '')} {c.get('value_b', c.get('indicator_b', ''))}"
            if bool(res.iloc[-1]):
                passed_buy.append(desc)
            else:
                failed_buy.append(desc)

        return {
            "triggered": buy_triggered or sell_triggered,
            "side": side,
            "symbol": symbol,
            "current_values": current_values,
            "passed_buy_conditions": passed_buy,
            "failed_buy_conditions": failed_buy,
            "checked_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"조건 체크 오류: {e}")
        raise HTTPException(status_code=500, detail=f"조건 체크 실패: {str(e)}")
