<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# web

## Purpose
React-based web dashboard for real-time monitoring and control of the trading bot. Provides visualization of portfolio performance, active positions, and trading activity.

## Key Files

| File | Description |
|------|-------------|
| `package.json` | Node.js dependencies and build scripts |
| `package-lock.json` | Exact dependency versions |
| `src/index.css` | Main CSS stylesheet |
| `dist/` | Built React application assets |
| `public/` | Static public assets (favicon, etc.) |

## For AI Agents

### Working In This Directory
- This is a frontend React application using Vite as the build tool
- The dashboard communicates with the Python backend via WebSocket and REST API
- All real-time updates come through WebSocket connections
- Chart visualizations use Recharts library

### Build Commands

```bash
# Install dependencies
npm install

# Development server (with hot reload)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Architecture

```
┌─────────────────────────────────────────┐
│         Web Dashboard (React)           │
│  - Portfolio overview                   │
│  - Real-time charts                     │
│  - Active positions                     │
│  - Trade history                        │
└───────────────┬─────────────────────────┘
                │
                │ WebSocket + REST API
                │
┌───────────────▼─────────────────────────┐
│     Python Backend (FastAPI)            │
│     (feature_source/ui_web.py)          │
│  - Serves static files                  │
│  - WebSocket endpoint                   │
│  - REST API endpoints                   │
└─────────────────────────────────────────┘
```

### Key Features

#### 1. Portfolio Overview
- Total portfolio value with real-time updates
- Unrealized and realized PnL
- Cash balance
- Performance metrics (Sharpe ratio, win rate, etc.)

#### 2. Real-Time Charts
- Portfolio value over time
- PnL curve
- Strategy performance comparison
- Drawdown visualization

#### 3. Active Positions
- List of all open positions
- Current market prices
- Unrealized PnL per position
- Quick close position buttons

#### 4. Trade History
- Complete trade log
- Filters by strategy, date, outcome
- Export to CSV functionality

#### 5. Bot Control
- Start/stop trading
- Enable/disable individual strategies
- Emergency stop button
- Configuration updates

### Component Structure

```
src/
├── App.jsx                    # Main application component
├── components/
│   ├── PortfolioOverview.jsx  # Portfolio summary cards
│   ├── Chart.jsx              # Recharts wrapper
│   ├── PositionList.jsx       # Active positions table
│   ├── TradeHistory.jsx       # Trade history table
│   └── BotControls.jsx        # Start/stop buttons
├── hooks/
│   ├── useWebSocket.js        # WebSocket connection hook
│   └── usePortfolioData.js    # Portfolio data fetching
└── utils/
    └── formatters.js          # Number/currency formatting
```

### WebSocket Integration

```javascript
import { useEffect, useState } from 'react';

export function useWebSocket(url) {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      setData(message);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    };

    return () => {
      ws.close();
    };
  }, [url]);

  return { data, connected };
}
```

### REST API Integration

```javascript
import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

export async function getPortfolioData() {
  const response = await axios.get(`${API_BASE}/portfolio`);
  return response.data;
}

export async function getTradeHistory(filters = {}) {
  const response = await axios.get(`${API_BASE}/trades`, { params: filters });
  return response.data;
}

export async function closePosition(positionId) {
  const response = await axios.post(`${API_BASE}/positions/${positionId}/close`);
  return response.data;
}

export async function updateConfig(config) {
  const response = await axios.put(`${API_BASE}/config`, config);
  return response.data;
}
```

### Chart Visualization (Recharts)

```javascript
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

function PortfolioChart({ data }) {
  return (
    <LineChart width={800} height={400} data={data}>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey="timestamp" />
      <YAxis />
      <Tooltip />
      <Legend />
      <Line type="monotone" dataKey="total_value" stroke="#8884d8" name="Portfolio Value" />
      <Line type="monotone" dataKey="realized_pnl" stroke="#82ca9d" name="Realized PnL" />
    </LineChart>
  );
}
```

### Backend API Endpoints

The Python backend (`ui_web.py`) provides:

```python
from fastapi import FastAPI
from fastapi.websockets import WebSocket

app = FastAPI()

# REST API
@app.get("/api/portfolio")
async def get_portfolio():
    """Get current portfolio state"""
    return portfolio_manager.get_state()

@app.get("/api/trades")
async def get_trades(
    strategy: Optional[str] = None,
    days: int = 7
):
    """Get trade history with filters"""
    return pnl_database.get_trade_history(strategy, days)

@app.post("/api/positions/{position_id}/close")
async def close_position(position_id: str):
    """Close a specific position"""
    return trading_engine.close_position(position_id)

@app.put("/api/config")
async def update_config(config: dict):
    """Update bot configuration"""
    return config_manager.update(config)

# WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time updates for portfolio and trades"""
    await websocket.accept()
    try:
        while True:
            # Send portfolio updates
            await websocket.send_json({
                "type": "portfolio_update",
                "data": portfolio_manager.get_state()
            })
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        print("WebSocket disconnected")
```

## Dependencies

### Internal
- `feature_source/ui_web.py` - Backend FastAPI server
- `feature_source/bot_core.py` - Trading engine for control operations

### External (Node.js)
- `react` - UI framework
- `react-dom` - React DOM renderer
- `recharts` - Charting library
- `axios` - HTTP client
- `vite` - Build tool and dev server

### External (Python)
- `fastapi` - Web backend framework
- `uvicorn` - ASGI server
- `websockets` - WebSocket support

## Common Patterns

### Data Fetching Hook

```javascript
import { useState, useEffect } from 'axios';

function usePortfolioData() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await axios.get('/api/portfolio');
        setData(response.data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, []);

  return { data, loading, error };
}
```

### Currency Formatting

```javascript
export function formatCurrency(value) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatPercentage(value) {
  return new Intl.NumberFormat('en-US', {
    style: 'percent',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value / 100);
}
```

### Error Handling

```javascript
export function ErrorBoundary({ children }) {
  const [hasError, setHasError] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const handleError = (error) => {
      setHasError(true);
      setError(error);
    };

    window.addEventListener('error', handleError);
    return () => window.removeEventListener('error', handleError);
  }, []);

  if (hasError) {
    return (
      <div className="error-boundary">
        <h2>Something went wrong</h2>
        <pre>{error?.message}</pre>
        <button onClick={() => window.location.reload()}>
          Reload Page
        </button>
      </div>
    );
  }

  return children;
}
```

## Development Workflow

```bash
# Terminal 1: Start Python backend
cd feature_source
uv run main.py --web-only

# Terminal 2: Start React dev server
cd web
npm run dev

# Access dashboard at:
# - Frontend: http://localhost:5173 (Vite dev server)
# - Backend: http://localhost:8000 (FastAPI)
```

## Production Deployment

```bash
# Build React app
cd web
npm run build

# Copy dist/ to feature_source/web/dist/
# The Python backend will serve these static files

# Start production server
cd feature_source
uv run main.py --web-only --port 80
```

<!-- MANUAL: -->
