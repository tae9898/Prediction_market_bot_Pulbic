import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '@/api/client'
import type { PerformanceData, PortfolioSnapshot } from '@/api/types'

interface UsePerformanceReturn {
  performance: PerformanceData | null
  portfolioHistory: PortfolioSnapshot[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function usePerformance(walletId?: string, hours = 24, period = '7d'): UsePerformanceReturn {
  const [performance, setPerformance] = useState<PerformanceData | null>(null)
  const [portfolioHistory, setPortfolioHistory] = useState<PortfolioSnapshot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      setError(null)
      const [perfData, history] = await Promise.all([
        apiClient.getPerformance(walletId, hours),
        apiClient.getPortfolioHistory(walletId, period),
      ])
      setPerformance(perfData)
      setPortfolioHistory(history)
      setLoading(false)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch performance'
      setError(message)
      setLoading(false)
    }
  }, [walletId, hours, period])

  const refetch = useCallback(async () => {
    await fetchData()
  }, [fetchData])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return {
    performance,
    portfolioHistory,
    loading,
    error,
    refetch,
  }
}

export default usePerformance
