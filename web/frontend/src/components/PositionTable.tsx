import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { cn, formatCurrency, formatPercentage, getSignalBg, getSignalColor } from '@/utils/cn'
import type { PositionInfo } from '@/api/types'

interface PositionTableProps {
  positions: PositionInfo[]
  loading?: boolean
  className?: string
}

export function PositionTable({ positions, loading, className }: PositionTableProps) {
  if (loading) {
    return (
      <div className={cn('space-y-3', className)}>
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-16 rounded-lg bg-surface animate-pulse" />
        ))}
      </div>
    )
  }

  if (positions.length === 0) {
    return (
      <div className={cn('text-center py-12', className)}>
        <p className="text-text3 text-sm">No open positions</p>
      </div>
    )
  }

  return (
    <div className={cn('space-y-2', className)}>
      {positions.map((position, index) => (
        <motion.div
          key={`${position.wallet_id}-${position.asset}-${index}`}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: index * 0.05 }}
          className={cn(
            'group rounded-lg border border-border bg-surface p-4',
            'hover:border-primary/30 hover:bg-surface2 transition-all duration-200',
            'table-row-hover'
          )}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4 flex-1">
              {/* Asset Icon */}
              <div
                className={cn(
                  'w-10 h-10 rounded-lg flex items-center justify-center',
                  getSignalBg(position.side)
                )}
              >
                {position.side === 'UP' ? (
                  <TrendingUp size={18} className={getSignalColor(position.side)} />
                ) : (
                  <TrendingDown size={18} className={getSignalColor(position.side)} />
                )}
              </div>

              {/* Position Info */}
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-text font-semibold">{position.asset}</span>
                  <span
                    className={cn(
                      'px-2 py-0.5 rounded text-xs font-medium',
                      getSignalBg(position.side)
                    )}
                  >
                    {position.side}
                  </span>
                  <span className="text-text3 text-xs">via {position.strategy}</span>
                </div>
                <p className="text-text3 text-sm">{position.market}</p>
              </div>
            </div>

            {/* Size & Cost */}
            <div className="text-right">
              <p className="text-text font-mono text-sm">{position.size.toFixed(2)} contracts</p>
              <p className="text-text3 text-xs">Cost: {formatCurrency(position.cost)}</p>
            </div>

            {/* Prices */}
            <div className="text-right">
              <p className="text-text font-mono text-sm">{formatCurrency(position.cur_price)}</p>
              <p className="text-text3 text-xs">Avg: {formatCurrency(position.avg_price)}</p>
            </div>

            {/* PnL */}
            <div className="text-right min-w-[100px]">
              <p
                className={cn(
                  'font-display font-bold text-lg',
                  position.pnl >= 0 ? 'text-success' : 'text-error'
                )}
              >
                {position.pnl >= 0 ? '+' : ''}
                {formatCurrency(position.pnl)}
              </p>
              <p
                className={cn(
                  'text-xs font-mono',
                  position.pnl_pct >= 0 ? 'text-success' : 'text-error'
                )}
              >
                {formatPercentage(position.pnl_pct)}
              </p>
            </div>

            {/* Value */}
            <div className="text-right min-w-[80px]">
              <p className="text-text font-display font-semibold">
                {formatCurrency(position.current_value)}
              </p>
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  )
}

export default PositionTable
