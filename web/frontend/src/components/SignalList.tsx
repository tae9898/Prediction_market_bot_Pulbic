import { motion } from 'framer-motion'
import { Activity, TrendingUp, TrendingDown, Clock } from 'lucide-react'
import { cn, formatTimestamp, getSignalColor, getSignalBg } from '@/utils/cn'
import type { SignalEvent } from '@/api/types'

interface SignalListProps {
  signals: SignalEvent[]
  loading?: boolean
  className?: string
}

export function SignalList({ signals, loading, className }: SignalListProps) {
  const getSignalIcon = (message: string) => {
    const upper = message.toUpperCase()
    if (upper.includes('SUREBET') || upper.includes('ENTRY')) {
      return { icon: TrendingUp, type: 'success' }
    }
    if (upper.includes('EXIT') || upper.includes('SHORT')) {
      return { icon: TrendingDown, type: 'error' }
    }
    if (upper.includes('WAITING') || upper.includes('HEDGE')) {
      return { icon: Clock, type: 'warning' }
    }
    return { icon: Activity, type: 'neutral' }
  }

  if (loading) {
    return (
      <div className={cn('space-y-2', className)}>
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-12 rounded bg-surface animate-pulse" />
        ))}
      </div>
    )
  }

  if (signals.length === 0) {
    return (
      <div className={cn('text-center py-8', className)}>
        <p className="text-text3 text-sm">No signals yet</p>
      </div>
    )
  }

  return (
    <div className={cn('space-y-2', className)}>
      {signals.slice(0, 10).map((signal, index) => {
        const { icon: Icon, type } = getSignalIcon(signal.message)

        return (
          <motion.div
            key={`${signal.timestamp}-${index}`}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.03 }}
            className={cn(
              'flex items-start gap-3 p-3 rounded-lg border border-border bg-surface',
              'hover:border-primary/20 hover:bg-surface2 transition-all duration-200'
            )}
          >
            <div
              className={cn(
                'mt-0.5 p-1.5 rounded',
                type === 'success' && 'bg-success/10 text-success',
                type === 'error' && 'bg-error/10 text-error',
                type === 'warning' && 'bg-warning/10 text-warning',
                type === 'neutral' && 'bg-text3/10 text-text3'
              )}
            >
              <Icon size={14} strokeWidth={2} />
            </div>

            <div className="flex-1 min-w-0">
              <p className="text-text text-sm font-mono break-all leading-relaxed">
                {signal.message}
              </p>
              <div className="flex items-center gap-2 mt-1">
                <p className="text-text3 text-xs">{formatTimestamp(new Date(signal.timestamp).getTime() / 1000)}</p>
                {signal.wallet_id && (
                  <>
                    <span className="text-text3/30">•</span>
                    <p className="text-text3 text-xs">Wallet {signal.wallet_id}</p>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}

export default SignalList
