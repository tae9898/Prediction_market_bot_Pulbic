import axios from 'axios'
import type {
  WalletInfo,
  PositionInfo,
  MarketData,
  PerformanceData,
  SignalEvent,
  BotStatus,
  PortfolioSnapshot,
  PnLRecord,
} from './types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 503) {
      console.error('Trading engine not initialized')
    }
    return Promise.reject(error)
  }
)

export const apiClient = {
  // Status
  async getStatus(): Promise<BotStatus> {
    const response = await api.get<BotStatus>('/api/status')
    return response.data
  },

  // Wallets
  async getWallets(): Promise<WalletInfo[]> {
    const response = await api.get<WalletInfo[]>('/api/wallets')
    return response.data
  },

  async getWallet(walletId: string): Promise<WalletInfo> {
    const response = await api.get<WalletInfo>(`/api/wallets/${walletId}`)
    return response.data
  },

  async toggleAutoTrade(walletId: string): Promise<{ wallet_id: string; auto_trade: boolean; message: string }> {
    const response = await api.post(`/api/wallets/${walletId}/toggle-auto-trade`)
    return response.data
  },

  // Positions
  async getPositions(walletId?: string): Promise<PositionInfo[]> {
    const params = walletId ? { wallet_id: walletId } : {}
    const response = await api.get<PositionInfo[]>('/api/positions', { params })
    return response.data
  },

  // Markets
  async getMarkets(walletId?: string): Promise<MarketData[]> {
    const params = walletId ? { wallet_id: walletId } : {}
    const response = await api.get<MarketData[]>('/api/markets', { params })
    return response.data
  },

  // Performance
  async getPerformance(walletId?: string, hours = 24): Promise<PerformanceData> {
    const params: Record<string, string | number> = { hours }
    if (walletId) params.wallet_id = walletId
    const response = await api.get<PerformanceData>('/api/performance', { params })
    return response.data
  },

  // Signals
  async getSignals(limit = 50): Promise<SignalEvent[]> {
    const response = await api.get<SignalEvent[]>('/api/signals', { params: { limit } })
    return response.data
  },

  // Portfolio
  async getPortfolioHistory(walletId?: string, period = '7d'): Promise<PortfolioSnapshot[]> {
    const params: Record<string, string> = { period }
    if (walletId) params.wallet_id = walletId
    const response = await api.get<PortfolioSnapshot[]>('/api/portfolio', { params })
    return response.data
  },

  // Trades
  async getTrades(walletId?: string, asset?: string, limit = 100): Promise<PnLRecord[]> {
    const params: Record<string, string | number> = { limit }
    if (walletId) params.wallet_id = walletId
    if (asset) params.asset = asset
    const response = await api.get<PnLRecord[]>('/api/trades', { params })
    return response.data
  },

  // Health
  async healthCheck(): Promise<{ status: string; timestamp: string; engine_initialized: boolean }> {
    const response = await api.get('/health')
    return response.data
  },
}

export default api
