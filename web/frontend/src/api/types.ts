export interface WalletInfo {
  id: string
  address: string
  usdc_balance: number
  reserved_balance: number
  portfolio_value: number
  is_connected: boolean
  auto_trade: boolean
}

export interface PositionInfo {
  wallet_id: string
  asset: string
  market: string
  side: string
  size: number
  avg_price: number
  cur_price: number
  cost: number
  current_value: number
  pnl: number
  pnl_pct: number
  strategy: string
  entry_prob: number
}

export interface MarketData {
  asset: string
  price: number
  change_24h: number
  change_pct: number
  volatility: number
  momentum: string
  strike_price: number
  time_remaining: string
  time_remaining_sec: number
  up_ask: number
  up_bid: number
  down_ask: number
  down_bid: number
  spread: number
  fair_up: number
  fair_down: number
  edge_up: number
  edge_down: number
  d2: number
  surebet_profitable: boolean
  surebet_profit_rate: number
  signal: string
}

export interface PnLRecord {
  id: number
  timestamp: number
  wallet_id: string
  asset: string
  asset_name: string
  direction: string
  size: number
  price: number
  cost: number
  strategy: string
  is_exit: boolean
  realized_pnl: number
  condition_id: string
}

export interface PnLSnapshot {
  id: number
  timestamp: number
  wallet_id: string
  asset: string
  total_pnl: number
  realized_pnl: number
  unrealized_pnl: number
  position_size: number
  portfolio_value: number
}

export interface PerformanceStats {
  total_trades: number
  total_realized_pnl: number
  win_count: number
  loss_count: number
  win_rate: number
  avg_pnl: number
}

export interface StrategyPerformance {
  strategy: string
  trade_count: number
  win_count: number
  loss_count: number
  win_rate: number
  total_pnl: number
  avg_pnl: number
}

export interface PerformanceData {
  snapshots: PnLSnapshot[]
  stats: PerformanceStats
  strategy_performance: StrategyPerformance[]
}

export interface SignalEvent {
  timestamp: string
  wallet_id: string
  message: string
}

export interface BotStatus {
  is_running: boolean
  wallet_count: number
  total_portfolio_value: number
  total_usdc: number
  total_invested: number
  total_pnl: number
  update_count: number
  last_update: string
  logs: string[]
}

export interface PortfolioSnapshot {
  timestamp: number
  date_str: string
  usdc_balance: number
  invested_value: number
  total_value: number
}

export interface WebSocketMessage {
  type: string
  data?: Record<string, any>
  timestamp: number
}

export interface StateUpdate {
  usdc_balance: number
  portfolio_value: number
  assets: Record<string, {
    price: number
    signal: string
    has_position: boolean
    position_pnl: number
  }>
}
