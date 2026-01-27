"""
전략 및 거래소 레지스트리 시스템

전략과 거래소 클래스를 등록하고 관리하는 중앙 레지스트리를 제공합니다.
데코레이터를 통한 자동 발견을 지원합니다.
"""

import logging
import inspect
from typing import Type, Dict, Optional, Any, List, Callable
from functools import wraps

from core.interfaces.strategy_base import BaseStrategy, StrategyConfig
from core.interfaces.exchange_base import ExchangeClient


# 레지스트리 전역 인스턴스
_strategy_registry: Dict[str, Type[BaseStrategy]] = {}
_exchange_registry: Dict[str, Type[ExchangeClient]] = {}


class RegistrationError(Exception):
    """등록 오류"""
    pass


class ValidationError(Exception):
    """검증 오류"""
    pass


class StrategyRegistry:
    """
    전략 레지스트리

    전략 클래스를 등록하고 검증하며 인스턴스를 생성합니다.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        초기화

        Args:
            logger: 로거 (선택)
        """
        self.logger = logger or logging.getLogger("registry.strategy")
        self._strategies: Dict[str, Type[BaseStrategy]] = {}

    def register(
        self,
        name: str,
        strategy_class: Type[BaseStrategy],
        validate: bool = True
    ) -> None:
        """
        전략 클래스 등록

        Args:
            name: 전략 이름 (고유 ID)
            strategy_class: 전략 클래스 (BaseStrategy 상속)
            validate: 등록 시 검증 여부

        Raises:
            RegistrationError: 등록 실패 시
            ValidationError: 검증 실패 시
        """
        # 중복 등록 확인
        if name in self._strategies:
            self.logger.warning(f"전략 '{name}'이 이미 등록되어 있습니다. 덮어씁니다.")

        # 타입 검증
        if not inspect.isclass(strategy_class):
            raise RegistrationError(
                f"'{name}'은 클래스가 아닙니다: {type(strategy_class)}"
            )

        if not issubclass(strategy_class, BaseStrategy):
            raise RegistrationError(
                f"'{name}'은 BaseStrategy를 상속받지 않았습니다"
            )

        # 검증 실행
        if validate:
            try:
                self._validate_strategy(strategy_class)
            except Exception as e:
                raise ValidationError(f"전략 '{name}' 검증 실패: {e}") from e

        # 등록
        self._strategies[name] = strategy_class
        self.logger.info(f"전략 등록 완료: {name} ({strategy_class.__name__})")

    def get(self, name: str) -> Optional[Type[BaseStrategy]]:
        """
        등록된 전략 클래스 조회

        Args:
            name: 전략 이름

        Returns:
            Type[BaseStrategy]: 전략 클래스 (없으면 None)
        """
        return self._strategies.get(name)

    def create(
        self,
        name: str,
        config: StrategyConfig,
        **kwargs: Any
    ) -> Optional[BaseStrategy]:
        """
        전략 인스턴스 생성

        Args:
            name: 전략 이름
            config: 전략 설정
            **kwargs: 추가 인자 (logger 등)

        Returns:
            BaseStrategy: 생성된 인스턴스 (없으면 None)

        Raises:
            RegistrationError: 전략을 찾을 수 없을 때
        """
        strategy_class = self.get(name)

        if strategy_class is None:
            raise RegistrationError(f"전략을 찾을 수 없습니다: {name}")

        # 인스턴스 생성
        try:
            strategy = strategy_class(config, **kwargs)
            self.logger.info(f"전략 인스턴스 생성: {name}")
            return strategy
        except Exception as e:
            self.logger.error(f"전략 인스턴스 생성 실패 ({name}): {e}")
            raise

    def list_available(self) -> List[str]:
        """
        등록된 전략 이름 목록

        Returns:
            List[str]: 전략 이름 리스트
        """
        return list(self._strategies.keys())

    def is_registered(self, name: str) -> bool:
        """
        전략 등록 여부 확인

        Args:
            name: 전략 이름

        Returns:
            bool: 등록 여부
        """
        return name in self._strategies

    def unregister(self, name: str) -> bool:
        """
        전략 등록 해제

        Args:
            name: 전략 이름

        Returns:
            bool: 해제 성공 여부
        """
        if name in self._strategies:
            del self._strategies[name]
            self.logger.info(f"전략 등록 해제: {name}")
            return True
        return False

    def clear(self) -> None:
        """모든 전략 등록 해제"""
        count = len(self._strategies)
        self._strategies.clear()
        self.logger.info(f"모든 전략 등록 해제: {count}개")

    def _validate_strategy(self, strategy_class: Type[BaseStrategy]) -> None:
        """
        전략 클래스 검증

        Args:
            strategy_class: 전략 클래스

        Raises:
            ValidationError: 검증 실패 시
        """
        # 필수 메서드 확인
        required_methods = ["validate_config", "analyze"]

        for method_name in required_methods:
            if not hasattr(strategy_class, method_name):
                raise ValidationError(
                    f"필수 메서드가 없습니다: {method_name}"
                )

            method = getattr(strategy_class, method_name)

            if not callable(method):
                raise ValidationError(
                    f"'{method_name}'은 호출 가능해야 합니다"
                )

        # 추상 메서드 구현 확인
        abstract_methods = strategy_class.__abstractmethods__

        if abstract_methods:
            raise ValidationError(
                f"추상 메서드가 구현되지 않았습니다: {abstract_methods}"
            )

    def __len__(self) -> int:
        """등록된 전략 수"""
        return len(self._strategies)

    def __contains__(self, name: str) -> bool:
        """포함 여부 확인 (in 연산자)"""
        return name in self._strategies

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"StrategyRegistry(strategies={len(self._strategies)})"


class ExchangeRegistry:
    """
    거래소 레지스트리

    거래소 클라이언트 클래스를 등록하고 검증하며 인스턴스를 생성합니다.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        초기화

        Args:
            logger: 로거 (선택)
        """
        self.logger = logger or logging.getLogger("registry.exchange")
        self._exchanges: Dict[str, Type[ExchangeClient]] = {}

    def register(
        self,
        name: str,
        exchange_class: Type[ExchangeClient],
        validate: bool = True
    ) -> None:
        """
        거래소 클래스 등록

        Args:
            name: 거래소 이름 (고유 ID)
            exchange_class: 거래소 클래스 (ExchangeClient 상속)
            validate: 등록 시 검증 여부

        Raises:
            RegistrationError: 등록 실패 시
            ValidationError: 검증 실패 시
        """
        # 중복 등록 확인
        if name in self._exchanges:
            self.logger.warning(f"거래소 '{name}'이 이미 등록되어 있습니다. 덮어씁니다.")

        # 타입 검증
        if not inspect.isclass(exchange_class):
            raise RegistrationError(
                f"'{name}'은 클래스가 아닙니다: {type(exchange_class)}"
            )

        if not issubclass(exchange_class, ExchangeClient):
            raise RegistrationError(
                f"'{name}'은 ExchangeClient를 상속받지 않았습니다"
            )

        # 검증 실행
        if validate:
            try:
                self._validate_exchange(exchange_class)
            except Exception as e:
                raise ValidationError(f"거래소 '{name}' 검증 실패: {e}") from e

        # 등록
        self._exchanges[name] = exchange_class
        self.logger.info(f"거래소 등록 완료: {name} ({exchange_class.__name__})")

    def get(self, name: str) -> Optional[Type[ExchangeClient]]:
        """
        등록된 거래소 클래스 조회

        Args:
            name: 거래소 이름

        Returns:
            Type[ExchangeClient]: 거래소 클래스 (없으면 None)
        """
        return self._exchanges.get(name)

    def create(
        self,
        name: str,
        **kwargs: Any
    ) -> Optional[ExchangeClient]:
        """
        거래소 인스턴스 생성

        Args:
            name: 거래소 이름
            **kwargs: 생성자 인자 (exchange_name, logger 등)

        Returns:
            ExchangeClient: 생성된 인스턴스 (없으면 None)

        Raises:
            RegistrationError: 거래소를 찾을 수 없을 때
        """
        exchange_class = self.get(name)

        if exchange_class is None:
            raise RegistrationError(f"거래소를 찾을 수 없습니다: {name}")

        # 인스턴스 생성
        try:
            exchange = exchange_class(**kwargs)
            self.logger.info(f"거래소 인스턴스 생성: {name}")
            return exchange
        except Exception as e:
            self.logger.error(f"거래소 인스턴스 생성 실패 ({name}): {e}")
            raise

    def list_available(self) -> List[str]:
        """
        등록된 거래소 이름 목록

        Returns:
            List[str]: 거래소 이름 리스트
        """
        return list(self._exchanges.keys())

    def is_registered(self, name: str) -> bool:
        """
        거래소 등록 여부 확인

        Args:
            name: 거래소 이름

        Returns:
            bool: 등록 여부
        """
        return name in self._exchanges

    def unregister(self, name: str) -> bool:
        """
        거래소 등록 해제

        Args:
            name: 거래소 이름

        Returns:
            bool: 해제 성공 여부
        """
        if name in self._exchanges:
            del self._exchanges[name]
            self.logger.info(f"거래소 등록 해제: {name}")
            return True
        return False

    def clear(self) -> None:
        """모든 거래소 등록 해제"""
        count = len(self._exchanges)
        self._exchanges.clear()
        self.logger.info(f"모든 거래소 등록 해제: {count}개")

    def _validate_exchange(self, exchange_class: Type[ExchangeClient]) -> None:
        """
        거래소 클래스 검증

        Args:
            exchange_class: 거래소 클래스

        Raises:
            ValidationError: 검증 실패 시
        """
        # 필수 메서드 확인
        required_methods = [
            "connect",
            "disconnect",
            "buy",
            "sell",
            "cancel_order",
            "get_position",
            "get_balance",
            "get_order_status"
        ]

        for method_name in required_methods:
            if not hasattr(exchange_class, method_name):
                raise ValidationError(
                    f"필수 메서드가 없습니다: {method_name}"
                )

            method = getattr(exchange_class, method_name)

            if not callable(method):
                raise ValidationError(
                    f"'{method_name}'은 호출 가능해야 합니다"
                )

        # 추상 메서드 구현 확인
        abstract_methods = exchange_class.__abstractmethods__

        if abstract_methods:
            raise ValidationError(
                f"추상 메서드가 구현되지 않았습니다: {abstract_methods}"
            )

    def __len__(self) -> int:
        """등록된 거래소 수"""
        return len(self._exchanges)

    def __contains__(self, name: str) -> bool:
        """포함 여부 확인 (in 연산자)"""
        return name in self._exchanges

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"ExchangeRegistry(exchanges={len(self._exchanges)})"


# 전역 레지스트리 인스턴스
strategy_registry = StrategyRegistry()
exchange_registry = ExchangeRegistry()


# 데코레이터 함수
def register_strategy(name: str, validate: bool = True) -> Callable:
    """
    전략 클래스 등록 데코레이터

    사용 예시:
        @register_strategy("trend")
        class TrendStrategy(BaseStrategy):
            pass

    Args:
        name: 전략 이름
        validate: 검증 여부

    Returns:
        Callable: 데코레이터 함수
    """
    def decorator(cls: Type[BaseStrategy]) -> Type[BaseStrategy]:
        strategy_registry.register(name, cls, validate=validate)
        return cls

    return decorator


def register_exchange(name: str, validate: bool = True) -> Callable:
    """
    거래소 클래스 등록 데코레이터

    사용 예시:
        @register_exchange("binance")
        class BinanceClient(ExchangeClient):
            pass

    Args:
        name: 거래소 이름
        validate: 검증 여부

    Returns:
        Callable: 데코레이터 함수
    """
    def decorator(cls: Type[ExchangeClient]) -> Type[ExchangeClient]:
        exchange_registry.register(name, cls, validate=validate)
        return cls

    return decorator


# 하위 호환성을 위한 전역 함수
def get_strategy(name: str) -> Optional[Type[BaseStrategy]]:
    """전역 전략 레지스트리에서 전략 조회"""
    return strategy_registry.get(name)


def get_exchange(name: str) -> Optional[Type[ExchangeClient]]:
    """전역 거래소 레지스트리에서 거래소 조회"""
    return exchange_registry.get(name)


def list_strategies() -> List[str]:
    """등록된 전략 목록"""
    return strategy_registry.list_available()


def list_exchanges() -> List[str]:
    """등록된 거래소 목록"""
    return exchange_registry.list_available()


__all__ = [
    # 클래스
    "StrategyRegistry",
    "ExchangeRegistry",
    # 예외
    "RegistrationError",
    "ValidationError",
    # 전역 인스턴스
    "strategy_registry",
    "exchange_registry",
    # 데코레이터
    "register_strategy",
    "register_exchange",
    # 유틸리티 함수
    "get_strategy",
    "get_exchange",
    "list_strategies",
    "list_exchanges",
]
