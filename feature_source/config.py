"""
BTC Polymarket ARB Bot V3 - Configuration Manager
설정 파일(config.json)을 로드하고 관리하는 모듈
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional, List
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


@dataclass
class Config:
    """봇 설정을 관리하는 데이터 클래스"""

    # API Credentials
    private_key: str = ""
    proxy_address: str = ""
    order_proxy_url: str = ""  # New: Proxy for Orders (py-clob-client)
    sportmonks_token: str = ""
    covalent_api_key: str = ""  # New: Covalent API Key
    polymarket_api_key: str = ""
    polymarket_api_secret: str = ""
    polymarket_passphrase: str = ""

    # Web3
    web3_rpc_url: str = "https://polygon-rpc.com"

    # Web Dashboard
    web_port: int = 8000

    # Trading Parameters
    bet_amount_usdc: float = 10.0
    edge_threshold_pct: float = 3.0
    max_position_size: float = 100.0
    use_kelly: bool = False

    # Volatility Settings
    volatility_window_minutes: int = 60

    # Sure-Bet
    surebet_enabled: bool = True

    # Trend Strategy Settings (Directional + Contrarian)
    trend_enabled: bool = True
    trend_mode: str = "auto"  # "directional", "contrarian", "auto"

    # Directional Settings
    edge_threshold_pct: float = 3.0

    # Contrarian Settings
    contrarian_entry_edge_min: float = 3.0
    contrarian_entry_edge_max: float = 10.0
    contrarian_exit_edge: float = 1.0
    contrarian_take_profit_pct: float = 3.0

    # Edge Calculation
    subtract_spread_from_edge: bool = True

    # Multi-Asset Support
    enabled_assets: List[str] = field(default_factory=lambda: ["BTC", "ETH"])

    # Edge Hedge Strategy
    edge_hedge_enabled: bool = True
    edge_hedge_min_edge_pct: float = 10.0  # 진입 최소 edge %
    edge_hedge_profit_threshold_pct: float = 7.0  # 수익 헤지 임계값
    edge_hedge_stoploss_pct: float = 15.0  # 스탑로스 헤지 임계값

    # Auto Redeem Settings
    auto_redeem_enabled: bool = True  # 자동 정산 기능 활성화 여부

    # Global Safety
    global_stoploss_pct: float = 20.0  # 전역 강제 헷지 기준 (-20%)

    # Expiry Sniper Strategy
    expiry_sniper_enabled: bool = False
    expiry_sniper_minutes_before: int = 15  # A: 마감 A분 전
    expiry_sniper_prob_threshold: float = 98.0  # B: 확률 B% 이상
    expiry_sniper_amount_usdc: float = 10.0  # C: C달러 매수
    expiry_sniper_max_times: int = 3  # D: 최대 D번
    expiry_sniper_interval_seconds: int = 60  # E: E초 간격
    sniper_hedge_prob_threshold: float = 90.0  # F: F% 이하로 떨어지면 헤지

    # Emergency
    emergency_cleanup_on_start: bool = False

    @classmethod
    def load(cls, config_path: str = "config.json", suffix: str = "") -> "Config":
        """JSON 파일에서 설정을 로드 (주석 지원, URL 안전, Suffix 지원)"""
        data = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    content = f.read()

                    # 정규식: "문자열" OR //주석
                    # 문자열 내의 //는 무시하고, 실제 주석만 제거함
                    pattern = r'("(?:\\.|[^"\\])*")|//.*'

                    def replace(match):
                        # 문자열이 매칭되면 그대로 반환, 주석이면 빈 문자열 반환
                        return match.group(1) if match.group(1) else ""

                    content_no_comments = re.sub(pattern, replace, content)

                    # Common JSON errors fix
                    # 1. Trailing commas: , } -> } and , ] -> ]
                    content_no_comments = re.sub(
                        r",\s*([}\]])", r"\1", content_no_comments
                    )

                    # 2. Python booleans: True -> true, False -> false (outside strings)
                    content_no_comments = content_no_comments.replace(
                        ": True", ": true"
                    ).replace(": False", ": false")

                    data = json.loads(content_no_comments)
            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse config file: {e}")
        else:
            print(f"[WARNING] Config file not found: {config_path}")
            print("[INFO] Using default configuration and environment variables")

        # Helper to get value with suffix or fallback to base
        def get_val(key, default, fallback=True):
            # 1. Try key + suffix (e.g., "bet_amount_usdc_1")
            suffixed_key = f"{key}{suffix}"
            if suffixed_key in data:
                return data[suffixed_key]
            # 2. Try base key (e.g., "bet_amount_usdc") - Inherit
            # Only fallback if suffixed_key not found
            if fallback and key in data:
                return data[key]
            # 3. Return default
            return default

        # Helper for env vars with suffix
        def get_env(key, default_val, fallback=True):
            # Env var suffix style: PRIVATE_KEY_1
            env_suffix = suffix.upper()
            # If suffix is empty, it's just the base key anyway
            if suffix:
                val = os.getenv(f"{key}{env_suffix}")
                if val:
                    return val
            else:
                # Base load
                val = os.getenv(key)
                if val:
                    return val

            # Fallback to base env if not specific and fallback is enabled
            # (Only applies if we are looking for a suffix but failed)
            if fallback and suffix:
                val = os.getenv(key)
                if val:
                    return val

            return default_val

        return cls(
            # Sensitive data: Env var -> Config file (suffixed) -> Config file (base) -> Default
            # Identity fields MUST NOT fallback to base (must be unique per wallet)
            private_key=get_env(
                "PRIVATE_KEY",
                get_val("private_key", "", fallback=False),
                fallback=False,
            ),
            proxy_address=get_env(
                "PROXY_ADDRESS",
                get_val("proxy_address", "", fallback=False),
                fallback=False,
            ),
            order_proxy_url=get_env("ORDER_PROXY_URL", get_val("order_proxy_url", "")),
            sportmonks_token=get_env(
                "SPORTMONKS_TOKEN", get_val("sportmonks_token", "")
            ),
            covalent_api_key=get_env(
                "COVALENT_API_KEY", get_val("covalent_api_key", "")
            ),
            polymarket_api_key=get_env(
                "POLYMARKET_API_KEY", get_val("polymarket_api_key", "")
            ),
            polymarket_api_secret=get_env(
                "POLYMARKET_API_SECRET", get_val("polymarket_api_secret", "")
            ),
            polymarket_passphrase=get_env(
                "POLYMARKET_PASSPHRASE", get_val("polymarket_passphrase", "")
            ),
            web3_rpc_url=get_env(
                "WEB3_RPC_URL", get_val("web3_rpc_url", "https://polygon-rpc.com")
            ),
            web_port=int(get_env("WEB_PORT", get_val("web_port", 8000))),
            # Non-sensitive data
            bet_amount_usdc=get_val("bet_amount_usdc", 10.0),
            edge_threshold_pct=get_val("edge_threshold_pct", 3.0),
            max_position_size=get_val("max_position_size", 100.0),
            use_kelly=get_val("use_kelly", False),
            volatility_window_minutes=get_val("volatility_window_minutes", 60),
            surebet_enabled=get_val("surebet_enabled", True),  # NEW
            trend_enabled=get_val("trend_enabled", True),
            trend_mode=get_val("trend_mode", "auto"),
            contrarian_entry_edge_min=get_val("contrarian_entry_edge_min", 3.0),
            contrarian_entry_edge_max=get_val("contrarian_entry_edge_max", 10.0),
            contrarian_exit_edge=get_val("contrarian_exit_edge", 1.0),
            contrarian_take_profit_pct=get_val("contrarian_take_profit_pct", 3.0),
            # Multi-Asset Support
            enabled_assets=get_val("enabled_assets", ["BTC", "ETH"]),
            # Edge Hedge Strategy
            edge_hedge_enabled=get_val("edge_hedge_enabled", True),
            edge_hedge_min_edge_pct=get_val("edge_hedge_min_edge_pct", 10.0),
            edge_hedge_profit_threshold_pct=get_val(
                "edge_hedge_profit_threshold_pct", 7.0
            ),
            edge_hedge_stoploss_pct=get_val("edge_hedge_stoploss_pct", 15.0),
            auto_redeem_enabled=get_val("auto_redeem_enabled", True),
            global_stoploss_pct=get_val("global_stoploss_pct", 20.0),
            # Expiry Sniper Strategy
            expiry_sniper_enabled=cls._parse_bool(
                None, get_val("expiry_sniper_enabled", False)
            ),
            expiry_sniper_minutes_before=get_val("expiry_sniper_minutes_before", 15),
            expiry_sniper_prob_threshold=get_val("expiry_sniper_prob_threshold", 98.0),
            expiry_sniper_amount_usdc=get_val("expiry_sniper_amount_usdc", 10.0),
            expiry_sniper_max_times=get_val("expiry_sniper_max_times", 3),
            expiry_sniper_interval_seconds=get_val(
                "expiry_sniper_interval_seconds", 60
            ),
            sniper_hedge_prob_threshold=get_val("sniper_hedge_prob_threshold", 90.0),
            # Emergency
            emergency_cleanup_on_start=cls._parse_bool(
                None, get_val("emergency_cleanup_on_start", False)
            ),
        )

    @staticmethod
    def _parse_bool(env_value: Optional[str], default: bool) -> bool:
        """환경변수 문자열을 불리언으로 변환"""
        if env_value is None:
            return default
        return str(env_value).lower() in ("true", "1", "yes", "on")

    def save(self, config_path: str = "config.json") -> None:
        """설정을 JSON 파일에 저장 (민감한 정보 제외)"""
        # Note: Save currently only saves the 'base' config structure.
        # Supporting saving with suffix is complex and maybe not needed for this bot's current scope.
        data = {
            # Sensitive fields are excluded from saving to config.json
            # to enforce using .env for credentials
            "bet_amount_usdc": self.bet_amount_usdc,
            "edge_threshold_pct": self.edge_threshold_pct,
            "max_position_size": self.max_position_size,
            "use_kelly": self.use_kelly,
            "volatility_window_minutes": self.volatility_window_minutes,
            "surebet_enabled": self.surebet_enabled,
            "trend_enabled": self.trend_enabled,
            "trend_mode": self.trend_mode,
            "contrarian_entry_edge_min": self.contrarian_entry_edge_min,
            "contrarian_entry_edge_max": self.contrarian_entry_edge_max,
            "contrarian_exit_edge": self.contrarian_exit_edge,
            "contrarian_take_profit_pct": self.contrarian_take_profit_pct,
            "subtract_spread_from_edge": self.subtract_spread_from_edge,
            "web3_rpc_url": self.web3_rpc_url,
            "web_port": self.web_port,
            "enabled_assets": self.enabled_assets,
            "edge_hedge_enabled": self.edge_hedge_enabled,
            "edge_hedge_min_edge_pct": self.edge_hedge_min_edge_pct,
            "edge_hedge_profit_threshold_pct": self.edge_hedge_profit_threshold_pct,
            "edge_hedge_stoploss_pct": self.edge_hedge_stoploss_pct,
            "auto_redeem_enabled": self.auto_redeem_enabled,
            "global_stoploss_pct": self.global_stoploss_pct,
            "expiry_sniper_enabled": self.expiry_sniper_enabled,
            "expiry_sniper_minutes_before": self.expiry_sniper_minutes_before,
            "expiry_sniper_prob_threshold": self.expiry_sniper_prob_threshold,
            "expiry_sniper_amount_usdc": self.expiry_sniper_amount_usdc,
            "expiry_sniper_max_times": self.expiry_sniper_max_times,
            "expiry_sniper_interval_seconds": self.expiry_sniper_interval_seconds,
            "sniper_hedge_prob_threshold": self.sniper_hedge_prob_threshold,
            "emergency_cleanup_on_start": self.emergency_cleanup_on_start,
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def is_valid(self) -> bool:
        """필수 설정이 유효한지 확인"""
        return bool(self.private_key and self.proxy_address)

    def __repr__(self) -> str:
        return (
            f"Config(bet_amount={self.bet_amount_usdc}, "
            f"edge_threshold={self.edge_threshold_pct}%, "
            f"trend={self.trend_mode})"
        )


# 싱글톤 설정 인스턴스
_config: Optional[Config] = None


def get_config(suffix: str = "") -> Config:
    """전역 설정 인스턴스 반환 (기본값) - Suffix 지원을 위해선 매번 로드하거나 캐싱 필요"""
    # For backward compatibility and simple usage, we return a cached base config if suffix is empty
    global _config
    if suffix == "":
        if _config is None:
            _config = Config.load(suffix=suffix)
        return _config
    else:
        # For specific wallet configs, load fresh (or we could cache them too)
        return Config.load(suffix=suffix)


def reload_config() -> Config:
    """설정 다시 로드"""
    global _config
    _config = Config.load()
    return _config
