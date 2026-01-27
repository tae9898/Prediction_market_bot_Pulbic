import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '@/api/client'
import type { BotStatus } from '@/api/types'

interface UseStatusReturn {
  status: BotStatus | null
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function useStatus(pollInterval = 2000): UseStatusReturn {
  const [status, setStatus] = useState<BotStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      setError(null)
      const data = await apiClient.getStatus()
      setStatus(data)
      setLoading(false)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch status'
      setError(message)
      setLoading(false)
    }
  }, [])

  const refetch = useCallback(async () => {
    await fetchStatus()
  }, [fetchStatus])

  useEffect(() => {
    fetchStatus()

    if (pollInterval > 0) {
      const interval = setInterval(fetchStatus, pollInterval)
      return () => clearInterval(interval)
    }
  }, [fetchStatus, pollInterval])

  return {
    status,
    loading,
    error,
    refetch,
  }
}

export default useStatus
