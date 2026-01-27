# Component Library

This document showcases all UI components used in the Trading Bot Dashboard.

## Design System

### Colors

| Color | Hex | Usage |
|-------|-----|-------|
| `background` | #0a0a0f | Main background |
| `surface` | #12121a | Card background |
| `primary` | #00ff9f | Success, positive trends |
| `accent` | #ff006e | Error, negative trends |
| `warning` | #ffbe0b | Warnings |
| `text` | #e0e0e0 | Primary text |
| `text2` | #a0a0b0 | Secondary text |
| `text3` | #606070 | Muted text |

### Typography

- **Display**: Orbitron (headers, numbers, data)
- **Body**: Inter (general text)
- **Mono**: Space Mono (data, addresses)

## Components

### StatusCard

Displays a single metric with optional trend indicator.

```tsx
<StatusCard
  title="Total Portfolio"
  value={12345.67}
  change={123.45}
  icon={Wallet}
  trend="up"
  size="md"
  glow
/>
```

**Props:**
- `title` - Card title
- `value` - Numeric or string value
- `change` - Optional percentage change
- `icon` - Lucide icon component
- `trend` - "up" | "down" | "neutral"
- `size` - "sm" | "md" | "lg"
- `glow` - Enable hover glow effect

### WalletCard

Interactive card for wallet information.

```tsx
<WalletCard
  wallet={walletInfo}
  onToggleAutoTrade={(id) => toggle(id)}
  onClick={() => navigate(`/wallet/${id}`)}
/>
```

**Features:**
- Connection status indicator
- Balance display
- Auto-trade toggle
- Hover effects and animations
- Click to navigate

### PositionTable

Table of open trading positions.

```tsx
<PositionTable
  positions={positions}
  loading={false}
/>
```

**Columns:**
- Asset and direction indicator
- Position size and cost
- Entry and current prices
- PnL with color coding
- Current value

### PerformanceChart

Interactive chart for portfolio or PnL history.

```tsx
<PerformanceChart
  data={portfolioHistory}
  type="portfolio"
/>
```

**Types:**
- `portfolio` - Area chart with gradient
- `pnl` - Line chart with multiple series

**Features:**
- Custom tooltip
- Responsive design
- Gradient fills
- Smooth animations

### SignalList

Scrollable list of trading signals.

```tsx
<SignalList
  signals={signals}
  loading={false}
/>
```

**Features:**
- Signal type icons
- Timestamp formatting
- Wallet attribution
- Staggered animations
- Auto-scroll to latest

### MarketGrid

Grid of market data cards.

```tsx
<MarketGrid
  markets={markets}
  loading={false}
/>
```

**Card Contents:**
- Asset name and momentum
- Current price and change
- Time remaining
- Spread and edge
- Surebet opportunities
- Signal badge
- UP/DOWN prices

### Header

App header with status indicators.

```tsx
<Header
  connected={true}
/>
```

**Features:**
- Logo with connection status
- Live/Offline indicator
- Active status badge
- Sticky positioning

## Utility Components

### Loading States

```tsx
{/* Skeleton loading */}
<div className="h-16 rounded bg-surface animate-pulse" />

{/* Custom skeleton */}
<div className="skeleton h-40 w-full" />
```

### Status Badges

```tsx
<span className={cn('px-2 py-1 rounded text-xs', getSignalBg(signal))}>
  {signal}
</span>
```

### Trend Indicators

```tsx
<div className={cn('flex items-center gap-1', trendColor)}>
  <TrendingUp size={14} />
  <span>+5.67%</span>
</div>
```

## Animation Patterns

### Staggered List

```tsx
{items.map((item, index) => (
  <motion.div
    key={item.id}
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: index * 0.05 }}
  >
    {item.content}
  </motion.div>
))}
```

### Hover Effects

```tsx
<motion.div
  whileHover={{ scale: 1.02 }}
  whileTap={{ scale: 0.98 }}
  className="transition-all duration-300"
>
  {content}
</motion.div>
```

### Page Transitions

```tsx
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.3 }}
>
  {pageContent}
</motion.div>
```

## Responsive Patterns

### Grid Layouts

```tsx
{/* Mobile: 1 col, Tablet: 2 col, Desktop: 3 col */}
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {cards}
</div>
```

### Hide on Mobile

```tsx
<div className="hidden md:block">
  {desktopContent}
</div>
```

## Best Practices

1. **Always use TypeScript** - Define prop interfaces
2. **Memoize expensive computations** - Use `useMemo`
3. **Stable callbacks** - Use `useCallback` for handlers
4. **Loading states** - Show skeleton during data fetch
5. **Error boundaries** - Wrap components in error boundaries
6. **Accessibility** - Add ARIA labels where needed
7. **Performance** - Avoid inline functions in JSX
8. **Consistency** - Follow existing component patterns
