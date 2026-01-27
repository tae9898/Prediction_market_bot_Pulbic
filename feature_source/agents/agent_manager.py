"""
BTC Polymarket ARB Bot V3 - Agent Manager
에이전트 관리 및 지식 조회
"""

import json
import os
from typing import Dict, Optional, Any
from datetime import datetime

from .polymarket_learning_agent import PolymarketLearningAgent


class AgentManager:
    """에이전트 관리자"""
    
    def __init__(self, config_path: str = None):
        """
        Args:
            config_path: 에이전트 설정 파일 경로
        """
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "agent_config.json")
        
        self.config = self._load_config(config_path)
        self.learning_agent = PolymarketLearningAgent(self.config)
        self._knowledge: Optional[Dict] = None
    
    def _load_config(self, path: str) -> Dict:
        """설정 파일 로드"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {
                "docs_url": "https://docs.polymarket.com",
                "cache_path": "polymarket_knowledge.json",
                "cache_ttl_hours": 24,
            }
    
    async def get_polymarket_knowledge(self) -> Dict:
        """
        Polymarket API 지식 로드 (캐시 또는 학습)
        
        Returns:
            학습된 지식 딕셔너리
        """
        # 캐시 확인
        cached = self._load_cache()
        if cached:
            self._knowledge = cached
            return cached
        
        # 학습 수행
        self._knowledge = await self.learning_agent.learn()
        
        # 캐시 저장
        self._save_cache(self._knowledge)
        
        return self._knowledge
    
    def _load_cache(self) -> Optional[Dict]:
        """캐시된 지식 로드"""
        cache_path = self.config.get("cache_path", "polymarket_knowledge.json")
        ttl_hours = self.config.get("cache_ttl_hours", 24)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # TTL 확인
            cached_time = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
            age_hours = (datetime.now() - cached_time).total_seconds() / 3600
            
            if age_hours > ttl_hours:
                return None
            
            return data.get("knowledge", {})
            
        except Exception:
            return None
    
    def _save_cache(self, knowledge: Dict) -> None:
        """지식을 캐시에 저장"""
        cache_path = self.config.get("cache_path", "polymarket_knowledge.json")
        
        try:
            data = {
                "timestamp": datetime.now().isoformat(),
                "knowledge": knowledge,
            }
            
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"[AgentManager] 캐시 저장 실패: {e}")
    
    def print_polymarket_summary(self) -> None:
        """학습된 지식 요약 출력"""
        if not self._knowledge:
            print("[AgentManager] 지식이 로드되지 않았습니다.")
            return
        
        print("\n" + "=" * 50)
        print("📚 Polymarket API Knowledge Summary")
        print("=" * 50)
        
        endpoints = self._knowledge.get("endpoints", {})
        for name, info in endpoints.items():
            print(f"\n🔹 {name}")
            print(f"   URL: {info.get('url', 'N/A')}")
            print(f"   Method: {info.get('method', 'GET')}")
            if info.get('description'):
                print(f"   Description: {info.get('description')[:100]}...")
        
        print("\n" + "=" * 50)
    
    def get_endpoint_info(self, endpoint_name: str) -> Optional[Dict]:
        """
        특정 엔드포인트 정보 조회
        
        Args:
            endpoint_name: 엔드포인트 이름 (예: "book", "order")
        
        Returns:
            엔드포인트 정보 딕셔너리
        """
        if not self._knowledge:
            return None
        
        return self._knowledge.get("endpoints", {}).get(endpoint_name)
    
    def get_code_example(self, example_name: str) -> Optional[str]:
        """
        코드 예제 가져오기
        
        Args:
            example_name: 예제 이름 (예: "init_client", "place_order")
        
        Returns:
            코드 예제 문자열
        """
        if not self._knowledge:
            return None
        
        return self._knowledge.get("examples", {}).get(example_name)
