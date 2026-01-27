"""
Expiry Sniper Strategy - 마감 직전 고확률 배팅 전략

전략 개요:
1. 마감 A분 전 (예: 15분)
2. 확률 B% 이상 (예: 98%) - 한쪽 방향이 확실할 때
3. C 달러만큼 매수
4. 최대 D번 진입
5. E초 간격으로 분할 매수
"""

import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Callable
from datetime import datetime

@dataclass
class SniperState:
    """자산별 스나이퍼 상태"""
    asset_type: str = ""
    executions_count: int = 0      # 실행 횟수
    last_execution_time: float = 0.0 # 마지막 실행 시간
    is_active: bool = False        # 현재 활성화 상태 (조건 충족 중)
    target_direction: str = ""     # 목표 방향 (UP/DOWN)

@dataclass
class SniperConfig:
    """스나이퍼 설정"""
    enabled: bool = True
    minutes_before: int = 15       # A
    prob_threshold: float = 98.0   # B
    amount_usdc: float = 10.0      # C
    max_times: int = 3             # D
    interval_seconds: int = 60     # E

class ExpirySniperStrategy:
    """마감 직전 고확률 스나이핑 전략"""
    
    def __init__(
        self,
        config: SniperConfig,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        self.config = config
        self._log_callback = log_callback
        
        # 자산별 상태
        self.states: Dict[str, SniperState] = {}
        
    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)
        else:
            print(message)
            
    def analyze(
        self,
        asset_type: str,
        time_remaining_sec: int,
        market_up_ask: float,
        market_down_ask: float,
        has_position: bool = False 
    ) -> Optional[Dict]:
        """
        스나이핑 기회 분석
        
        Returns:
            None: 실행 안함
            Dict: {
                "action": "BUY",
                "direction": "UP" or "DOWN",
                "amount": float,
                "reason": str
            }
        """
        if not self.config.enabled:
            return None
            
        # 상태 초기화 (필요시)
        if asset_type not in self.states:
            self.states[asset_type] = SniperState(asset_type=asset_type)
        
        state = self.states[asset_type]
        
        # 1. 시간 조건 체크 (A분 전)
        minutes_remaining = time_remaining_sec / 60
        if minutes_remaining > self.config.minutes_before:
            # 아직 시간 안됨 - 상태 리셋 (새로운 마켓 등)
            if state.executions_count > 0 and minutes_remaining > self.config.minutes_before * 2:
                 # 시간이 아주 많이 남았으면(다음 마켓) 카운트 리셋
                 state.executions_count = 0
            return None
            
        if time_remaining_sec <= 30: # 30초 미만은 너무 위험해서 스킵 (선택사항)
             return None

        # 2. 확률 조건 체크 (B% 이상)
        # Ask 가격을 확률로 간주 (매수 비용)
        prob_up = market_up_ask * 100
        prob_down = market_down_ask * 100
        
        target_dir = ""
        target_prob = 0.0
        
        if prob_up >= self.config.prob_threshold:
            target_dir = "UP"
            target_prob = prob_up
        elif prob_down >= self.config.prob_threshold:
            target_dir = "DOWN"
            target_prob = prob_down
            
        if not target_dir:
            return None
            
        # 3. 횟수 제한 체크 (최대 D번)
        if state.executions_count >= self.config.max_times:
            return None
            
        # 4. 간격 체크 (E초)
        if time.time() - state.last_execution_time < self.config.interval_seconds:
            return None
            
        # 실행 결정
        reason = f"Expiry Sniper: {minutes_remaining:.1f}m left, Prob {target_prob:.1f}% >= {self.config.prob_threshold}%"
        
        return {
            "action": "BUY",
            "direction": target_dir,
            "amount": self.config.amount_usdc,
            "reason": reason,
            "prob": target_prob
        }

    def record_execution(self, asset_type: str) -> None:
        """실행 기록 (성공 시 호출)"""
        if asset_type in self.states:
            self.states[asset_type].executions_count += 1
            self.states[asset_type].last_execution_time = time.time()
            self._log(f"[{asset_type}] Sniper 실행 완료 ({self.states[asset_type].executions_count}/{self.config.max_times})")
