"""
에이전트 상태 API 라우터
GET /api/agents - 에이전트 상태 목록
GET /api/agents/logs - 에이전트 로그
POST /api/agents/{agent_type}/start - 에이전트 시작
POST /api/agents/{agent_type}/stop - 에이전트 중지
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from core.database import get_db
from models.agent_log import AgentLog
from schemas.agent import AgentStatusResponse, AgentLogResponse

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/", response_model=List[AgentStatusResponse])
async def get_agents():
    """모든 에이전트 상태 조회"""
    from main import (
        market_analyzer_agent,
        strategy_agent,
        risk_manager_agent,
        execution_agent,
        portfolio_agent,
    )

    agents = [
        market_analyzer_agent,
        strategy_agent,
        risk_manager_agent,
        execution_agent,
        portfolio_agent,
    ]

    return [
        AgentStatusResponse(**agent.get_status())
        for agent in agents
        if agent is not None
    ]


@router.get("/logs", response_model=List[AgentLogResponse])
async def get_agent_logs(
    agent_type: str = Query(None),
    level: str = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 로그 조회"""
    query = select(AgentLog).order_by(desc(AgentLog.created_at))

    if agent_type:
        query = query.where(AgentLog.agent_type == agent_type)
    if level:
        query = query.where(AgentLog.level == level)

    query = query.limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        AgentLogResponse(
            id=log.id,
            agent_id=log.agent_id,
            agent_type=log.agent_type,
            level=log.level,
            message=log.message,
            data=log.data,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.post("/{agent_type}/start")
async def start_agent(agent_type: str):
    """에이전트 시작"""
    from main import (
        market_analyzer_agent, strategy_agent,
        risk_manager_agent, execution_agent, portfolio_agent,
        AGENT_INTERVALS,
    )

    agent_map = {
        "market_analyzer": market_analyzer_agent,
        "strategy": strategy_agent,
        "risk_manager": risk_manager_agent,
        "execution": execution_agent,
        "portfolio": portfolio_agent,
    }

    agent = agent_map.get(agent_type)
    if agent is None:
        return {"success": False, "message": f"에이전트를 찾을 수 없습니다: {agent_type}"}

    interval = AGENT_INTERVALS.get(agent_type, 60)
    await agent.start(interval_seconds=interval)
    return {"success": True, "message": f"{agent_type} 에이전트 시작됨"}


@router.post("/{agent_type}/stop")
async def stop_agent(agent_type: str):
    """에이전트 중지"""
    from main import (
        market_analyzer_agent, strategy_agent,
        risk_manager_agent, execution_agent, portfolio_agent,
    )

    agent_map = {
        "market_analyzer": market_analyzer_agent,
        "strategy": strategy_agent,
        "risk_manager": risk_manager_agent,
        "execution": execution_agent,
        "portfolio": portfolio_agent,
    }

    agent = agent_map.get(agent_type)
    if agent is None:
        return {"success": False, "message": f"에이전트를 찾을 수 없습니다: {agent_type}"}

    await agent.stop()
    return {"success": True, "message": f"{agent_type} 에이전트 중지됨"}
