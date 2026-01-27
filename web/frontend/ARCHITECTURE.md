# Frontend Architecture

## Design Philosophy

The trading bot dashboard follows a **cyberpunk-inspired dark theme** with emphasis on:
- **Real-time data visualization** through WebSocket connections
- **Micro-interactions** and smooth animations using Framer Motion
- **Responsive design** that works across all screen sizes
- **Type safety** with TypeScript throughout
- **Performance optimization** with lazy loading and efficient re-renders

## Technology Choices

| Technology | Purpose | Rationale |
|------------|---------|-----------|
| React 18 | UI Framework | Component-based architecture, excellent ecosystem |
| TypeScript | Type System | Catch errors at compile time, better IDE support |
| Vite | Build Tool | Fast HMR, optimized production builds |
| Tailwind CSS | Styling | Rapid development, consistent design system |
| Framer Motion | Animations | Declarative animations, better performance than CSS |
| Recharts | Charts | React-native charts, customizable |
| Axios | HTTP Client | Interceptors, request/response transformation |
| React Router | Routing | Declarative routing, code splitting |

## Directory Structure

```
src/
├── api/               # API layer
│   ├── client.ts      # Axios instance with interceptors
│   └── types.ts       # TypeScript interfaces for API responses
├── components/        # UI components (presentational)
│   ├── Header.tsx     # App header
│   ├── StatusCard.tsx # Metric card component
│   ├── WalletCard.tsx # Wallet card with hover effects
│   ├── PositionTable.tsx # Table of open positions
│   ├── PerformanceChart.tsx # Line/area charts
│   ├── SignalList.tsx # List of trading signals
│   └── MarketGrid.tsx # Grid of market data cards
├── hooks/            # Custom React hooks (data layer)
│   ├── useWebSocket.ts    # WebSocket connection manager
│   ├── useWallets.ts      # Wallet data fetching
│   ├── useStatus.ts       # Bot status polling
│   ├── usePerformance.ts  # Performance data
│   └── useSignals.ts      # Signal history
├── pages/            # Page-level components (routing)
│   ├── Dashboard.tsx      # Main dashboard
│   ├── WalletDetail.tsx   # Individual wallet view
│   └── NotFound.tsx       # 404 page
├── styles/           # Global styles
│   └── index.css     # Tailwind imports + custom CSS
├── utils/            # Utility functions
│   └── cn.ts         # Class name utils, formatters
├── App.tsx           # Root component with routing
└── main.tsx          # Entry point
```

## Component Architecture

### Component Hierarchy

```
App (Router + WebSocket)
├── Dashboard
│   ├── Header
│   ├── StatusCard (x4)
│   ├── WalletCard (xN)
│   ├── PositionTable
│   ├── PerformanceChart
│   ├── SignalList
│   └── MarketGrid
└── WalletDetail
    ├── Header
    ├── StatusCard (x4)
    ├── PerformanceChart
    ├── PositionTable
    └── MarketGrid
```

### Component Types

1. **Presentational Components** (`components/`)
   - Receive data via props
   - No direct API calls
   - Focus on UI and animations
   - Example: `StatusCard`, `WalletCard`

2. **Container Components** (`pages/`)
   - Orchestrate data fetching
   - Manage local state
   - Compose presentational components
   - Example: `Dashboard`, `WalletDetail`

3. **Custom Hooks** (`hooks/`)
   - Encapsulate data logic
   - Handle loading/error states
   - Provide clean API to components
   - Example: `useWallets`, `useWebSocket`

## Data Flow

```
User Action
    ↓
Component Event Handler
    ↓
Hook Function (useWallets, etc.)
    ↓
API Client (axios)
    ↓
Backend API
    ↓
Response Transformation
    ↓
State Update
    ↓
Component Re-render
```

## WebSocket Integration

The WebSocket connection is managed at the App level:

1. **Connection Lifecycle**
   - Auto-connect on mount
   - Reconnect on disconnect (3s interval)
   - Clean disconnect on unmount

2. **Message Types**
   - `connected` - Initial connection确认
   - `state_update` - Real-time state changes (every 1s)
   - `auto_trade_toggled` - Auto-trade status change
   - `pong` - Response to ping

3. **State Propagation**
   - Global WebSocket in App component
   - Message handlers trigger state updates
   - Components react to state changes

## Performance Optimizations

1. **Debouncing**
   - WebSocket state updates throttled
   - Polling intervals configurable

2. **Memoization**
   - `useMemo` for expensive calculations
   - `useCallback` for event handlers

3. **Code Splitting**
   - Route-based code splitting (future)
   - Lazy loading for charts (future)

4. **Efficient Re-renders**
   - Stable component references
   - Key props for lists
   - Minimal prop drilling

## State Management

The dashboard uses **React Hooks + Context** for state:

- **Local State**: `useState` for component-specific state
- **Server State**: Custom hooks wrapping API calls
- **Global State**: WebSocket state in App (passed via props)
- **URL State**: React Router for navigation

**Note**: No Redux/Recoil is used as the app doesn't have complex global state needs.

## Styling System

### Tailwind Configuration

Custom colors defined in `tailwind.config.js`:

```js
colors: {
  background: '#0a0a0f',  // Main background
  surface: '#12121a',     // Card background
  surface2: '#1a1a24',    // Hover background
  border: '#2a2a3a',      // Border color
  primary: '#00ff9f',     // Green accent (success)
  accent: '#ff006e',      // Pink accent (error)
  // ... more
}
```

### Custom CSS

Additional styles in `styles/index.css`:
- Custom scrollbar
- Grid pattern background
- Noise texture overlay
- Glow effects
- Signal badge styles
- Skeleton loading
- Cyberpunk border effect

### Animation System

Using Framer Motion:
- `fade-in` - Opacity transitions
- `slide-up` - Y-axis translations
- `scale` - Hover effects
- Staggered animations for lists

## API Integration

### Axios Configuration

```typescript
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
})

// Request interceptor - add auth (future)
// Response interceptor - handle errors
```

### Error Handling

- 503: Engine not initialized
- 404: Resource not found
- Network errors: Show user-friendly message
- Timeouts: Retry with backoff

## Testing Strategy (Future)

1. **Unit Tests**
   - Utility functions
   - Custom hooks
   - Component rendering

2. **Integration Tests**
   - API client
   - WebSocket connection
   - User flows

3. **E2E Tests**
   - Critical user paths
   - WebSocket reconnection
   - Error scenarios

## Deployment

### Build Process

```bash
npm run build
```

Outputs to `dist/` with:
- Minified JS/CSS
- Asset hashing
- Optimized bundles
- Source maps

### Environment Variables

- `VITE_API_URL` - Backend API URL
- `VITE_WS_URL` - WebSocket URL

### Production Considerations

- API URL should point to production backend
- WebSocket should use WSS (secure)
- Enable CORS for frontend domain
- Add authentication tokens
- Enable gzip compression on server
