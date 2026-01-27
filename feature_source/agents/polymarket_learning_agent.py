"""
BTC Polymarket ARB Bot V3 - Polymarket Learning Agent
Polymarket 공식 문서 학습 에이전트
"""

import asyncio
import re
from typing import Dict, List, Optional
from dataclasses import dataclass

try:
    import aiohttp
except ImportError:
    aiohttp = None


@dataclass
class EndpointInfo:
    """API 엔드포인트 정보"""
    name: str
    url: str
    method: str = "GET"
    description: str = ""
    parameters: Dict = None
    example: str = ""


class PolymarketLearningAgent:
    """
    Polymarket API 학습 에이전트
    
    공식 문서를 크롤링하고 파싱하여 API 정보를 추출
    """
    
    # 기본 지식 (문서 접근 불가 시)
    DEFAULT_KNOWLEDGE = {
        "endpoints": {
            "book": {
                "url": "https://clob.polymarket.com/book",
                "method": "GET",
                "description": "Get orderbook for a token",
                "parameters": {"token_id": "Token ID to get book for"},
            },
            "markets": {
                "url": "https://gamma-api.polymarket.com/events",
                "method": "GET",
                "description": "Get market events and information",
                "parameters": {"slug": "Market slug identifier"},
            },
            "order": {
                "url": "https://clob.polymarket.com/order",
                "method": "POST",
                "description": "Place a new order",
                "parameters": {"order": "Signed order object"},
            },
            "cancel": {
                "url": "https://clob.polymarket.com/cancel",
                "method": "DELETE",
                "description": "Cancel an existing order",
                "parameters": {"orderId": "Order ID to cancel"},
            },
        },
        "examples": {
            "init_client": '''
from py_clob_client.client import ClobClient

client = ClobClient(
    host="https://clob.polymarket.com",
    key=PRIVATE_KEY,
    chain_id=137,  # Polygon
    signature_type=2,  # POLY_GNOSIS_SAFE
)
''',
            "place_order": '''
from py_clob_client.clob_types import MarketOrderArgs

order_args = MarketOrderArgs(
    token_id=TOKEN_ID,
    amount=10.0,  # USDC
)

response = client.create_and_post_order(order_args)
''',
            "get_book": '''
# Using aiohttp
async with aiohttp.ClientSession() as session:
    url = f"https://clob.polymarket.com/book?token_id={token_id}"
    async with session.get(url) as resp:
        book = await resp.json()
        bids = book.get("bids", [])
        asks = book.get("asks", [])
''',
        },
        "auth": {
            "signature_type": 2,
            "description": "POLY_GNOSIS_SAFE signature for Polygon network",
            "api_creds": "Use create_or_derive_api_creds() to generate API credentials",
        },
    }
    
    def __init__(self, config: Dict):
        """
        Args:
            config: 에이전트 설정
        """
        self.config = config
        self.base_url = config.get("docs_url", "https://docs.polymarket.com")
    
    async def learn(self) -> Dict:
        """
        공식 문서 학습 수행
        
        Returns:
            학습된 지식 딕셔너리
        """
        if aiohttp is None:
            print("[LearningAgent] aiohttp 미설치, 기본 지식 사용")
            return self.DEFAULT_KNOWLEDGE
        
        knowledge = {
            "endpoints": {},
            "examples": {},
            "auth": {},
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                # 주요 문서 페이지 학습
                endpoints_config = self.config.get("endpoints", {})
                
                for name, path in endpoints_config.items():
                    url = f"{self.base_url}{path}"
                    content = await self._fetch_page(session, url)
                    
                    if content:
                        parsed = self._parse_documentation(content)
                        knowledge["endpoints"].update(parsed.get("endpoints", {}))
                        knowledge["examples"].update(parsed.get("examples", {}))
            
            # 기본 지식으로 보충
            if not knowledge["endpoints"]:
                knowledge = self.DEFAULT_KNOWLEDGE
            else:
                # 누락된 엔드포인트 보충
                for key, value in self.DEFAULT_KNOWLEDGE["endpoints"].items():
                    if key not in knowledge["endpoints"]:
                        knowledge["endpoints"][key] = value
                
                for key, value in self.DEFAULT_KNOWLEDGE["examples"].items():
                    if key not in knowledge["examples"]:
                        knowledge["examples"][key] = value
            
            return knowledge
            
        except Exception as e:
            print(f"[LearningAgent] 학습 오류: {e}")
            return self.DEFAULT_KNOWLEDGE
    
    async def _fetch_page(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """페이지 내용 가져오기"""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception:
            pass
        return None
    
    def _parse_documentation(self, content: str) -> Dict:
        """문서 파싱"""
        result = {
            "endpoints": {},
            "examples": {},
        }
        
        # 코드 블록 추출
        code_blocks = re.findall(r'```(\w+)?\n(.*?)```', content, re.DOTALL)
        
        for lang, code in code_blocks:
            if lang in ('python', 'py'):
                # Python 코드 예제 저장
                if 'ClobClient' in code:
                    result["examples"]["init_client"] = code.strip()
                elif 'MarketOrderArgs' in code or 'OrderArgs' in code:
                    result["examples"]["place_order"] = code.strip()
        
        # API 엔드포인트 추출
        endpoint_patterns = [
            r'(GET|POST|PUT|DELETE)\s+(/\w+(?:/\w+)*)',
            r'`(https?://[^`]+)`',
        ]
        
        for pattern in endpoint_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    method, path = match
                    name = path.split('/')[-1]
                    result["endpoints"][name] = {
                        "url": path,
                        "method": method,
                    }
        
        return result
    
    async def relearn_on_error(self, error_message: str) -> Dict:
        """
        에러 발생 시 재학습
        
        Args:
            error_message: 발생한 에러 메시지
        
        Returns:
            업데이트된 지식
        """
        print(f"[LearningAgent] 에러 기반 재학습: {error_message}")
        return await self.learn()
