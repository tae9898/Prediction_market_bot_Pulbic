# API Quick Reference

## Base URL
```
http://localhost:8000
```

## Authentication
Currently no authentication (add for production)

---

## REST Endpoints

### `GET /`
API information and available endpoints

**Response:**
```json
{
  "name": "Trading Bot API",
  "version": "1.0.0",
  "status": "running",
  "endpoints": {...}
}
```

---

### `GET /api/status`
Overall bot status

**Response:**
```json
{
  "is_running": true,
  "wallet_count": 2,
  "total_portfolio_value": 3000.0,
  "total_usdc": 2500.0,
  "total_invested": 500.0,
  "total_pnl": 50.0,
  "update_count": 1234,
  "last_update": "10:30:45",
  "logs": ["[10:30:45] ..."]
}
```

---

### `GET /api/wallets`
List all wallets

**Response:**
```json
[
  {
    "id": "0",
    "address": "0x...",
    "usdc_balance": 1000.0,
    "reserved_balance": 100.0,
    "portfolio_value": 1500.0,
    "is_connected": true,
    "auto_trade": true
  }
]
```

---

### `GET /api/wallets/{wallet_id}`
Specific wallet details

**Parameters:**
- `wallet_id` (path): Wallet ID (e.g., "0", "1")

**Response:** Same as `/api/wallets` but single object

---

### `GET /api/positions`
All positions across wallets

**Query Parameters:**
- `wallet_id` (optional): Filter by wallet

**Response:**
```json
[
  {
    "wallet_id": "0",
    "asset": "BTC",
    "market": "BTC Hourly",
    "side": "UP",
    "size": 10.0,
    "avg_price": 0.5,
    "cur_price": 0.55,
    "cost": 5.0,
    "current_value": 5.5,
    "pnl": 0.5,
    "pnl_pct": 10.0,
    "strategy": "edge_hedge_entry",
    "entry_prob": 85.0
  }
]
```

---

### `GET /api/markets`
Market data for all assets

**Query Parameters:**
- `wallet_id` (optional): Filter by wallet

**Response:**
```json
[
  {
    "asset": "BTC",
    "price": 95000.0,
    "change_24h": 1000.0,
    "change_pct": 1.06,
    "volatility": 0.15,
    "momentum": "BULLISH",
    "strike_price": 95000.0,
    "time_remaining": "45:00",
    "time_remaining_sec": 2700,
    "up_ask": 0.52,
    "up_bid": 0.50,
    "down_ask": 0.50,
    "down_bid": 0.48,
    "spread": 0.02,
    "fair_up": 0.51,
    "fair_down": 0.49,
    "edge_up": 1.0,
    "edge_down": 1.0,
    "d2": 0.5,
    "surebet_profitable": false,
    "surebet_profit_rate": 0.0,
    "signal": "WAITING"
  }
]
```

---

### `GET /api/performance`
PnL history and performance stats

**Query Parameters:**
- `wallet_id` (optional): Filter by wallet
- `hours` (default: 24): Hours of history

**Response:**
```json
{
  "snapshots": [
    {
      "id": 1,
      "timestamp": 1737972000.0,
      "wallet_id": "0",
      "asset": "BTC",
      "total_pnl": 50.0,
      "realized_pnl": 30.0,
      "unrealized_pnl": 20.0,
      "position_size": 10.0,
      "portfolio_value": 1500.0
    }
  ],
  "stats": {
    "total_trades": 25,
    "total_realized_pnl": 150.0
  },
  "strategy_performance": [
    {
      "strategy": "edge_hedge_entry",
      "trade_count": 10,
      "win_count": 7,
      "loss_count": 3,
      "win_rate": 70.0,
      "total_pnl": 80.0,
      "avg_pnl": 8.0
    }
  ]
}
```

---

### `GET /api/signals`
Recent trading signals

**Query Parameters:**
- `limit` (default: 50): Max signals

**Response:**
```json
[
  {
    "timestamp": "2025-01-27T10:30:45",
    "wallet_id": "0",
    "message": "[10:30:45] [BTC] Signal: SUREBET +1.5%"
  }
]
```

---

### `GET /api/portfolio`
Portfolio value history

**Query Parameters:**
- `wallet_id` (optional): Filter by wallet
- `period` (default: "7d"): "1d", "7d", "all"

**Response:**
```json
[
  {
    "timestamp": 1737972000.0,
    "date_str": "2025-01-27 10:30:00",
    "usdc_balance": 1000.0,
    "invested_value": 500.0,
    "total_value": 1500.0
  }
]
```

---

### `GET /api/trades`
Trade history

**Query Parameters:**
- `wallet_id` (optional): Filter by wallet
- `asset` (optional): Filter by asset
- `limit` (default: 100): Max trades

**Response:**
```json
[
  {
    "id": 1,
    "timestamp": 1737972000.0,
    "wallet_id": "0",
    "asset": "BTC",
    "asset_name": "BTC > 95000",
    "direction": "UP",
    "size": 10.0,
    "price": 0.5,
    "cost": 5.0,
    "strategy": "edge_hedge_entry",
    "is_exit": false,
    "realized_pnl": 0.0,
    "condition_id": "0x..."
  }
]
```

---

### `POST /api/wallets/{wallet_id}/toggle-auto-trade`
Toggle auto-trading

**Response:**
```json
{
  "wallet_id": "0",
  "auto_trade": false,
  "message": "Auto-trade disabled"
}
```

---

### `GET /health`
Health check

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-27T10:30:45.123456",
  "engine_initialized": true
}
```

---

## WebSocket

### Connection
```
ws://localhost:8000/ws
```

### Client → Server Commands

**Get State:**
```json
{
  "command": "get_state",
  "wallet_id": "0"
}
```

**Toggle Auto-Trade:**
```json
{
  "command": "toggle_auto_trade",
  "wallet_id": "0"
}
```

**Ping:**
```json
{
  "command": "ping"
}
```

### Server → Client Messages

**Connected:**
```json
{
  "type": "connected",
  "data": {
    "message": "Connected to trading bot",
    "wallet_count": 2
  },
  "timestamp": 1737972000.0
}
```

**State Update (every 1s):**
```json
{
  "type": "state_update",
  "data": {
    "usdc_balance": 1000.0,
    "portfolio_value": 1500.0,
    "assets": {
      "BTC": {
        "price": 95000.0,
        "signal": "WAITING",
        "has_position": true,
        "position_pnl": 0.5
      }
    }
  },
  "timestamp": 1737972000.0
}
```

**Auto-Trade Toggled:**
```json
{
  "type": "auto_trade_toggled",
  "data": {
    "wallet_id": "0",
    "auto_trade": false
  },
  "timestamp": 1737972000.0
}
```

**Pong:**
```json
{
  "type": "pong",
  "timestamp": 1737972000.0
}
```

---

## Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Error Responses

All endpoints may return errors:

```json
{
  "detail": "Error message here"
}
```

Common HTTP status codes:
- `400`: Bad Request
- `404`: Not Found
- `503`: Service Unavailable (engine not initialized)
