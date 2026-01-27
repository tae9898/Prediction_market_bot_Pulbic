import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '@/api/client'
import type { WalletInfo, PositionInfo, MarketData } from '@/api/types'

interface WalletData {
  info: WalletInfo
  positions: PositionInfo[]
  markets: MarketData[]
}

interface UseWalletsReturn {
  wallets: WalletData[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
  getWallet: (id: string) => WalletData | undefined
  toggleAutoTrade: (id: string) => Promise<void>
}

export function useWallets(pollInterval = 5000): UseWalletsReturn {
  const [wallets, setWallets] = useState<WalletData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchWallets = useCallback(async () => {
    try {
      setError(null)
      const [walletsInfo, positions, markets] = await Promise.all([
        apiClient.getWallets(),
        apiClient.getPositions(),
        apiClient.getMarkets(),
      ])

      // Combine data by wallet
      const walletData: WalletData[] = walletsInfo.map((info) => ({
        info,
        positions: positions.filter((p) => p.wallet_id === info.id),
        markets: markets, // Markets are shared across all wallets
      }))

      setWallets(walletData)
      setLoading(false)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch wallets'
      setError(message)
      setLoading(false)
    }
  }, [])

  const refetch = useCallback(async () => {
    await fetchWallets()
  }, [fetchWallets])

  const getWallet = useCallback(
    (id: string) => {
      return wallets.find((w) => w.info.id === id)
    },
    [wallets]
  )

  const toggleAutoTrade = useCallback(async (id: string) => {
    try {
      await apiClient.toggleAutoTrade(id)
      await fetchWallets()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to toggle auto-trade'
      setError(message)
      throw err
    }
  }, [fetchWallets])

  useEffect(() => {
    fetchWallets()

    if (pollInterval > 0) {
      const interval = setInterval(fetchWallets, pollInterval)
      return () => clearInterval(interval)
    }
  }, [fetchWallets, pollInterval])

  return {
    wallets,
    loading,
    error,
    refetch,
    getWallet,
    toggleAutoTrade,
  }
}

export default useWallets
