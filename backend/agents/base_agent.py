"""
OpenClaw BaseAgent - 모든 에이전트의 기본 추상 클래스
에이전트 수명주기, 로깅, 상태 관리를 담당합니다.
"""
import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Optional, Any

from loguru import logger


class AgentStatus(str, Enum):
    """에이전트 실행 상태"""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    ANALYZING = "ANALYZING"
    EXECUTING = "EXECUTING"
    ERROR = "ERROR"
    STOPPED = "STOPPED"


class AgentSignal:
    """에이전트 간 통신 신호 기본 클래스"""

    def __init__(self, source_agent: str, signal_type: str, data: dict):
        self.id = str(uuid.uuid4())
        self.source_agent = source_agent
        self.signal_type = signal_type
        self.data = data
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_agent": self.source_agent,
            "signal_type": self.signal_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseAgent(ABC):
    """
    OpenClaw 기본 에이전트 클래스
    
    모든 에이전트는 이 클래스를 상속하고
    run_cycle() 메서드를 반드시 구현해야 합니다.
    
    사용 방법:
        class MyAgent(BaseAgent):
            agent_type = "my_agent"
            
            async def run_cycle(self):
                # 에이전트 로직 구현
                ...
    """

    agent_type: str = "base"

    def __init__(self, agent_id: Optional[str] = None):
        self.agent_id = agent_id or f"{self.agent_type}_{uuid.uuid4().hex[:8]}"
        self.status = AgentStatus.IDLE
        self.error_count = 0
        self.total_cycles = 0
        self.last_run: Optional[datetime] = None
        self.started_at: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

        # DB 로그 저장 콜백 (main.py에서 주입)
        self._log_callback = None

        logger.info(f"에이전트 초기화: {self.agent_id} ({self.agent_type})")

    def set_log_callback(self, callback):
        """DB 로그 저장 콜백 설정"""
        self._log_callback = callback

    async def _log(self, level: str, message: str, data: Optional[dict] = None):
        """에이전트 활동 로깅 (콘솔 + DB)"""
        log_fn = getattr(logger, level.lower(), logger.info)
        log_fn(f"[{self.agent_id}] {message}")

        # DB 저장 (콜백이 있는 경우)
        if self._log_callback:
            try:
                await self._log_callback(
                    agent_id=self.agent_id,
                    agent_type=self.agent_type,
                    level=level,
                    message=message,
                    data=json.dumps(data) if data else None,
                )
            except Exception as e:
                logger.warning(f"에이전트 로그 DB 저장 실패: {e}")

    def _set_status(self, status: AgentStatus):
        """에이전트 상태 변경"""
        old_status = self.status
        self.status = status
        if old_status != status:
            logger.debug(f"[{self.agent_id}] 상태 변경: {old_status} → {status}")

    @abstractmethod
    async def run_cycle(self):
        """
        에이전트 1 사이클 실행 - 반드시 구현
        이 메서드가 주기적으로 호출됩니다.
        """
        ...

    async def start(self, interval_seconds: int = 60):
        """에이전트 백그라운드 실행 시작"""
        if self._running:
            logger.warning(f"[{self.agent_id}] 이미 실행 중")
            return

        self._running = True
        self.started_at = datetime.utcnow()
        self._set_status(AgentStatus.RUNNING)
        await self._log("INFO", f"에이전트 시작 (주기: {interval_seconds}초)")

        self._task = asyncio.create_task(
            self._run_loop(interval_seconds)
        )

    async def stop(self):
        """에이전트 중지"""
        self._running = False
        self._set_status(AgentStatus.STOPPED)

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self._log("INFO", f"에이전트 중지 (총 실행: {self.total_cycles}회)")

    async def _run_loop(self, interval_seconds: int):
        """에이전트 실행 루프"""
        while self._running:
            try:
                self._set_status(AgentStatus.ANALYZING)
                await self.run_cycle()
                self.total_cycles += 1
                self.last_run = datetime.utcnow()
                self.error_count = 0  # 성공 시 에러 카운트 초기화

            except asyncio.CancelledError:
                break

            except Exception as e:
                self.error_count += 1
                self._set_status(AgentStatus.ERROR)
                await self._log("ERROR", f"사이클 오류 (연속 {self.error_count}회): {e}", {"error": str(e)})

                # 연속 5회 오류 시 자동 중지
                if self.error_count >= 5:
                    await self._log("ERROR", "연속 오류 5회 초과, 에이전트 자동 중지")
                    self._running = False
                    break

                # 오류 시 대기 시간 증가 (지수 백오프)
                wait_time = min(interval_seconds * (2 ** self.error_count), 300)
                await asyncio.sleep(wait_time)
                continue

            finally:
                if self._running:
                    self._set_status(AgentStatus.IDLE)

            await asyncio.sleep(interval_seconds)

    def get_status(self) -> dict:
        """에이전트 상태 정보 반환"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "total_cycles": self.total_cycles,
            "error_count": self.error_count,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "is_running": self._running,
        }
