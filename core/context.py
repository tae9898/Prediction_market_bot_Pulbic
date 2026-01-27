"""
실행 컨텍스트

전략 실행을 위한 공유 상태와 콜백 메커니즘을 제공합니다.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, Awaitable
from enum import Enum


class BotState(Enum):
    """봇 상태"""
    IDLE = "idle"  # 대기 중
    RUNNING = "running"  # 실행 중
    STOPPING = "stopping"  # 중지 중
    STOPPED = "stopped"  # 중지됨
    ERROR = "error"  # 오류 발생


@dataclass
class ExecutionContext:
    """
    실행 컨텍스트

    전략 실행에 필요한 모든 상태와 콜백을 포함합니다.

    Attributes:
        bot_id: 봇 식별자
        current_time: 현재 시간 (타임스탬프)
        bot_state: 봇 상태
        running: 실행 플래그
        strategy_state: 전략별 상태 저장소
        assets: 자산 정보
        positions: 포지션 정보
        logs: 로그 목록
    """
    bot_id: str = "bot"
    current_time: float = field(default_factory=time.time)
    bot_state: BotState = BotState.IDLE
    running: bool = False

    # 상태 저장소
    strategy_state: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    assets: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    positions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    logs: list[Dict[str, Any]] = field(default_factory=list)

    # 로거
    logger: Optional[logging.Logger] = None

    # 콜백 함수
    log_callback: Optional[Callable[[str, str], None]] = None
    log_error_callback: Optional[Callable[[str], None]] = None
    log_pnl_callback: Optional[Callable[[str, float], None]] = None

    # 이벤트 콜백
    on_signal_callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None
    on_trade_callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None
    on_error_callback: Optional[Callable[[str, Exception], None]] = None

    # 설정
    max_log_entries: int = 1000
    auto_trade: bool = False

    def __post_init__(self):
        """초기화 검증 및 로거 설정"""
        if self.logger is None:
            self.logger = logging.getLogger(f"context.{self.bot_id}")

    # ===== 시간 관리 =====

    def update_time(self) -> float:
        """
        현재 시간 업데이트

        Returns:
            float: 업데이트된 시간
        """
        self.current_time = time.time()
        return self.current_time

    def get_time(self) -> float:
        """
        현재 시간 조회

        Returns:
            float: 현재 타임스탬프
        """
        return self.current_time

    # ===== 상태 관리 =====

    def set_bot_state(self, state: BotState) -> None:
        """
        봇 상태 설정

        Args:
            state: 새로운 상태
        """
        old_state = self.bot_state
        self.bot_state = state

        self.log(
            f"상태 변경: {old_state.value} → {state.value}",
            log_type="debug"
        )

    def get_bot_state(self) -> BotState:
        """
        봇 상태 조회

        Returns:
            BotState: 현재 상태
        """
        return self.bot_state

    def is_running(self) -> bool:
        """
        실행 중 여부 확인

        Returns:
            bool: 실행 중 여부
        """
        return self.running

    def start(self) -> None:
        """실행 시작"""
        self.running = True
        self.set_bot_state(BotState.RUNNING)

    def stop(self) -> None:
        """실행 중지"""
        self.running = False
        self.set_bot_state(BotState.STOPPED)

    # ===== 전략 상태 관리 =====

    def set_strategy_state(
        self,
        strategy_name: str,
        key: str,
        value: Any
    ) -> None:
        """
        전략 상태 저장

        Args:
            strategy_name: 전략 이름
            key: 상태 키
            value: 상태 값
        """
        if strategy_name not in self.strategy_state:
            self.strategy_state[strategy_name] = {}

        self.strategy_state[strategy_name][key] = value
        self.logger.debug(
            f"상태 저장 [{strategy_name}]: {key} = {value}"
        )

    def get_strategy_state(
        self,
        strategy_name: str,
        key: str,
        default: Any = None
    ) -> Any:
        """
        전략 상태 조회

        Args:
            strategy_name: 전략 이름
            key: 상태 키
            default: 기본값 (없으면 None)

        Returns:
            Any: 상태 값
        """
        if strategy_name not in self.strategy_state:
            return default

        return self.strategy_state[strategy_name].get(key, default)

    def get_all_strategy_state(
        self,
        strategy_name: str
    ) -> Dict[str, Any]:
        """
        전략의 모든 상태 조회

        Args:
            strategy_name: 전략 이름

        Returns:
            Dict[str, Any]: 상태 딕셔너리
        """
        return self.strategy_state.get(strategy_name, {}).copy()

    def clear_strategy_state(self, strategy_name: str) -> None:
        """
        전략 상태 초기화

        Args:
            strategy_name: 전략 이름
        """
        if strategy_name in self.strategy_state:
            del self.strategy_state[strategy_name]
            self.logger.debug(f"상태 초기화: {strategy_name}")

    # ===== 로깅 =====

    def log(self, message: str, log_type: str = "debug") -> None:
        """
        로그 기록

        Args:
            message: 로그 메시지
            log_type: 로그 타입 ("debug", "error", "pnl")
        """
        timestamp = time.time()

        # 로그 딕셔너리 생성
        log_entry = {
            "timestamp": timestamp,
            "message": message,
            "type": log_type,
            "bot_id": self.bot_id
        }

        # 로그 목록에 추가
        self.logs.append(log_entry)

        # 최대 로그 개수 제한
        if len(self.logs) > self.max_log_entries:
            self.logs.pop(0)

        # 로거에 기록
        if log_type == "error":
            self.logger.error(message)
            if self.log_error_callback:
                self.log_error_callback(message)
        elif log_type == "pnl":
            self.logger.info(f"[PNL] {message}")
            if self.log_pnl_callback:
                # PNL 메시지에서 수익 추출 시도
                try:
                    # 메시지 형식: "청산: LONG | 손익: +10.50 USDC | ..."
                    if "손익:" in message:
                        pnl_str = message.split("손익:")[1].split("USDC")[0].strip()
                        pnl_value = float(pnl_str.replace("+", ""))
                        self.log_pnl_callback(self.bot_id, pnl_value)
                except Exception:
                    pass
        else:
            self.logger.debug(message)

        # 사용자 정의 콜백
        if self.log_callback:
            try:
                self.log_callback(message, log_type)
            except Exception as e:
                self.logger.error(f"로그 콜백 오류: {e}")

    def log_error(self, message: str) -> None:
        """
        에러 로그 기록

        Args:
            message: 에러 메시지
        """
        self.log(message, log_type="error")

    def log_pnl(self, message: str) -> None:
        """
        손익 로그 기록

        Args:
            message: 손익 메시지
        """
        self.log(message, log_type="pnl")

    def get_logs(
        self,
        log_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> list[Dict[str, Any]]:
        """
        로그 조회

        Args:
            log_type: 필터링할 로그 타입 (None이면 전체)
            limit: 최대 로그 개수 (None이면 전체)

        Returns:
            list[Dict]: 로그 리스트
        """
        filtered_logs = self.logs

        # 타입 필터링
        if log_type:
            filtered_logs = [
                log for log in self.logs
                if log.get("type") == log_type
            ]

        # 개수 제한
        if limit:
            filtered_logs = filtered_logs[-limit:]

        return filtered_logs

    def clear_logs(self) -> None:
        """모든 로그 초기화"""
        self.logs.clear()
        self.logger.debug("로그 초기화")

    # ===== 이벤트 콜백 =====

    async def emit_signal(
        self,
        strategy_name: str,
        signal: Dict[str, Any]
    ) -> None:
        """
        시그널 이벤트 발생

        Args:
            strategy_name: 전략 이름
            signal: 시그널 데이터
        """
        self.log(
            f"시그널 발생 [{strategy_name}]: {signal.get('action')} | "
            f"{signal.get('direction')} | 에지: {signal.get('edge')}%"
        )

        if self.on_signal_callback:
            try:
                await self.on_signal_callback(strategy_name, signal)
            except Exception as e:
                self.log_error(f"시그널 콜백 오류: {e}")

    async def emit_trade(
        self,
        strategy_name: str,
        trade: Dict[str, Any]
    ) -> None:
        """
        거래 이벤트 발생

        Args:
            strategy_name: 전략 이름
            trade: 거래 데이터
        """
        self.log(
            f"거래 체결 [{strategy_name}]: {trade.get('side')} | "
            f"사이즈: {trade.get('size')} | 가격: {trade.get('price')}"
        )

        if self.on_trade_callback:
            try:
                await self.on_trade_callback(strategy_name, trade)
            except Exception as e:
                self.log_error(f"거래 콜백 오류: {e}")

    def emit_error(
        self,
        strategy_name: str,
        error: Exception
    ) -> None:
        """
        에러 이벤트 발생

        Args:
            strategy_name: 전략 이름
            error: 예외 객체
        """
        self.log_error(f"에러 발생 [{strategy_name}]: {error}")

        if self.on_error_callback:
            try:
                self.on_error_callback(strategy_name, error)
            except Exception as e:
                self.logger.error(f"에러 콜백 오류: {e}")

    # ===== 자산 및 포지션 관리 =====

    def update_asset(
        self,
        symbol: str,
        data: Dict[str, Any]
    ) -> None:
        """
        자산 정보 업데이트

        Args:
            symbol: 심볼
            data: 자산 데이터
        """
        self.assets[symbol] = data
        self.logger.debug(f"자산 업데이트: {symbol}")

    def get_asset(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        자산 정보 조회

        Args:
            symbol: 심볼

        Returns:
            Dict: 자산 데이터 (없으면 None)
        """
        return self.assets.get(symbol)

    def get_all_assets(self) -> Dict[str, Dict[str, Any]]:
        """
        모든 자산 정보 조회

        Returns:
            Dict: 자산 데이터 딕셔너리
        """
        return self.assets.copy()

    def update_position(
        self,
        symbol: str,
        position: Dict[str, Any]
    ) -> None:
        """
        포지션 정보 업데이트

        Args:
            symbol: 심볼
            position: 포지션 데이터
        """
        self.positions[symbol] = position
        self.logger.debug(f"포지션 업데이트: {symbol}")

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        포지션 정보 조회

        Args:
            symbol: 심볼

        Returns:
            Dict: 포지션 데이터 (없으면 None)
        """
        return self.positions.get(symbol)

    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        모든 포지션 정보 조회

        Returns:
            Dict: 포지션 데이터 딕셔너리
        """
        return self.positions.copy()

    def has_position(self, symbol: str) -> bool:
        """
        포지션 보유 여부 확인

        Args:
            symbol: 심볼

        Returns:
            bool: 포지션 보유 여부
        """
        return symbol in self.positions and bool(self.positions[symbol])

    # ===== 유틸리티 =====

    def to_dict(self) -> Dict[str, Any]:
        """
        딕셔너리로 변환

        Returns:
            Dict: 컨텍스트 데이터
        """
        return {
            "bot_id": self.bot_id,
            "current_time": self.current_time,
            "bot_state": self.bot_state.value,
            "running": self.running,
            "strategy_state": self.strategy_state.copy(),
            "assets": self.assets.copy(),
            "positions": self.positions.copy(),
            "auto_trade": self.auto_trade,
            "log_count": len(self.logs)
        }

    def reset(self) -> None:
        """컨텍스트 초기화"""
        self.current_time = time.time()
        self.bot_state = BotState.IDLE
        self.running = False
        self.strategy_state.clear()
        self.assets.clear()
        self.positions.clear()
        self.logs.clear()
        self.logger.debug("컨텍스트 초기화")

    def __repr__(self) -> str:
        """문자열 표현"""
        return (
            f"ExecutionContext("
            f"bot_id={self.bot_id}, "
            f"state={self.bot_state.value}, "
            f"running={self.running}, "
            f"strategies={len(self.strategy_state)}, "
            f"assets={len(self.assets)}, "
            f"positions={len(self.positions)}, "
            f"logs={len(self.logs)})"
        )


__all__ = [
    # 데이터 클래스
    "ExecutionContext",
    # 열거형
    "BotState",
]
