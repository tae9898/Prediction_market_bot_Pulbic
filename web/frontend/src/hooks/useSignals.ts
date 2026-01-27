import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '@/api/client'
import type { SignalEvent } from '@/api/types'

interface UseSignalsReturn {
  signals: SignalEvent[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function useSignals(limit = 50, pollInterval = 10000): UseSignalsReturn {
  const [signals, setSignals] = useState<SignalEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchSignals = useCallback(async () => {
    try {
      setError(null)
      const data = await apiClient.getSignals(limit)
      setSignals(data)
      setLoading(false)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch signals'
      setError(message)
      setLoading(false)
    }
  }, [limit])

  const refetch = useCallback(async () => {
    await fetchSignals()
  }, [fetchSignals])

  useEffect(() => {
    fetchSignals()

    if (pollInterval > 0) {
      const interval = setInterval(fetchSignals, pollInterval)
      return () => clearInterval(interval)
    }
  }, [fetchSignals, pollInterval])

  return {
    signals,
    loading,
    error,
    refetch,
  }
}

export default useSignals
