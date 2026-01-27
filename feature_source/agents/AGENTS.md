<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# agents

## Purpose
AI learning agents for analyzing Polymarket markets and optimizing trading decisions. This is an experimental module using machine learning to improve trading performance.

## Key Files

| File | Description |
|------|-------------|
| `agent_config.json` | Agent configuration including API endpoints and cache settings |
| `agent_manager.py` | Manager class for orchestrating multiple AI agents |
| `polymarket_learning_agent.py` | Polymarket-specific learning agent for market analysis |
| `__init__.py` | Python package initializer |
| `README.md` | Detailed documentation for AI agents |

## For AI Agents

### Working In This Directory
This is an experimental module. When making changes:
- Test agent decisions in simulation mode before live trading
- Monitor agent performance metrics closely
- Agent predictions should supplement, not replace, strategy logic
- Cache API responses to reduce costs and improve speed

### Agent Architecture

```python
from agents.agent_manager import AgentManager
from agents.polymarket_learning_agent import PolymarketLearningAgent

# Initialize agent manager
manager = AgentManager(config="agent_config.json")

# Create learning agent
agent = PolymarketLearningAgent(
    api_key=os.getenv("OPENAI_API_KEY"),
    cache_enabled=True
)

# Get trading recommendation
recommendation = await agent.analyze_market(
    market_id="12345",
    market_data={
        "yes_price": 0.65,
        "no_price": 0.36,
        "volume": 100000,
        "expiry": "2024-12-31"
    }
)

# Example output:
# {
#     "action": "BUY_YES",
#     "confidence": 0.78,
#     "reasoning": "Strong upward trend based on...",
#     "suggested_size": 50
# }
```

### Agent Configuration

```json
{
  "enabled": true,
  "model": "gpt-4",
  "temperature": 0.3,
  "max_tokens": 500,
  "cache_ttl": 300,
  "api_endpoint": "https://api.openai.com/v1/chat/completions",
  "rate_limit": {
    "requests_per_minute": 20,
    "tokens_per_minute": 40000
  }
}
```

### Integration with Strategies

```python
from strategies.edge_hedge import EdgeHedgeStrategy

class EdgeHedgeWithAI(EdgeHedgeStrategy):
    async def analyze(self, market_data: MarketData) -> Optional[TradeSignal]:
        # Get traditional signal
        signal = await super().analyze(market_data)

        # Enhance with AI agent
        if signal:
            ai_recommendation = await self.agent.analyze_market(market_data)
            if ai_recommendation["confidence"] < 0.7:
                # Skip low-confidence trades
                return None

            signal["size"] *= ai_recommendation["confidence"]
            signal["ai_reasoning"] = ai_recommendation["reasoning"]

        return signal
```

### Logging and Monitoring

```python
# Agent decisions are logged with:
# - Market ID
# - Timestamp
# - Recommendation
# - Confidence score
# - Actual outcome (for learning)

# Review agent performance
agent.get_performance_metrics(days=7)
# {
#     "total_recommendations": 150,
#     "accuracy": 0.72,
#     "avg_confidence": 0.68,
#     "profitable_trades": 108
# }
```

## Dependencies

### Internal
- `feature_source/config.py` - Configuration management
- `feature_source/models/probability.py` - Probability calculations for training
- `feature_source/exchanges/polymarket.py` - Market data for analysis

### External
- `openai` - OpenAI API for LLM-based agents
- `anthropic` - Anthropic API for Claude-based agents
- `requests` - HTTP client for API calls
- `diskcache` - Persistent caching for API responses

## Performance Considerations

### API Costs
- OpenAI GPT-4: ~$0.03-0.06 per 1K tokens
- Cache aggressive to reduce API calls
- Use smaller models (GPT-3.5) for rapid iterations
- Batch multiple market analyses in single API call

### Latency
- API calls can add 1-3 seconds latency
- Use caching for repeated queries
- Run agent analysis asynchronously
- Set timeouts to prevent hanging

### Rate Limiting
- OpenAI: 20-200 requests/minute depending on tier
- Implement backoff and retry logic
- Queue requests during high activity
- Fallback to rule-based if rate limited

## Common Patterns

### Caching Agent Responses

```python
from diskcache import Cache

cache = Cache("agent_cache")

def analyze_market_cached(market_id: str, market_data: dict):
    cache_key = f"market_{market_id}_{hash(str(market_data))}"

    if cached := cache.get(cache_key):
        return cached

    result = await agent.analyze_market(market_data)
    cache.set(cache_key, result, expire=300)  # 5 min TTL

    return result
```

### Confidence Thresholding

```python
MIN_CONFIDENCE = 0.7

if recommendation["confidence"] < MIN_CONFIDENCE:
    logger.warning(f"Low confidence: {recommendation['confidence']}")
    return None  # Skip trade
```

### Fallback to Rules

```python
try:
    signal = await agent.analyze_market(market_data)
except Exception as e:
    logger.error(f"Agent failed: {e}, falling back to rules")
    signal = rule_based_strategy.analyze(market_data)
```

## Future Enhancements

- **Reinforcement Learning**: Train models on historical trade outcomes
- **Ensemble Methods**: Combine multiple agent predictions
- **Real-time Learning**: Update agent based on live market feedback
- **Multi-agent Collaboration**: Specialized agents for different market types

<!-- MANUAL: -->
