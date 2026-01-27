import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Minus, Percent } from 'lucide-react'
import { cn, formatCurrency, formatPercentage, getSignalBg, getSignalColor, formatTimeRemaining } from '@/utils/cn'
import type { MarketData } from '@/api/types'

interface MarketGridProps {
  markets: MarketData[]
  loading?: boolean
  className?: string
}

export function MarketGrid({ markets, loading, className }: MarketGridProps) {
  if (loading) {
    return (
      <div className={cn('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4', className)}>
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-48 rounded-xl bg-surface animate-pulse" />
        ))}
      </div>
    )
  }

  if (markets.length === 0) {
    return (
      <div className={cn('text-center py-12', className)}>
        <p className="text-text3 text-sm">No markets available</p>
      </div>
    )
  }

  return (
    <div className={cn('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4', className)}>
      {markets.map((market, index) => {
        const trendIcon = market.change_pct >= 0 ? TrendingUp : market.change_pct <= 0 ? TrendingDown : Minus
        const trendColor = market.change_pct >= 0 ? 'text-success' : market.change_pct < 0 ? 'text-error' : 'text-text3'

        return (
          <motion.div
            key={`${market.asset}-${index}`}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.05 }}
            className={cn(
              'group relative overflow-hidden rounded-xl border border-border bg-surface p-4',
              'hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5',
              'transition-all duration-300'
            )}
          >
            {/* Background gradient */}
            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

            <div className="relative">
              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center bg-surface2')}>
                    <span className="text-text font-display font-bold text-sm">{market.asset[0]}</span>
                  </div>
                  <div>
                    <p className="text-text font-display font-semibold">{market.asset}</p>
                    <p className="text-text3 text-xs">{market.momentum}</p>
                  </div>
                </div>

                <div className={cn('flex items-center gap-1', trendColor)}>
                  <trendIcon size={14} />
                  <span className="text-sm font-mono font-medium">
                    {market.change_pct >= 0 ? '+' : ''}
                    {market.change_pct.toFixed(2)}%
                  </span>
                </div>
              </div>

              {/* Price */}
              <div className="mb-3">
                <p className="text-text font-display font-bold text-xl">
                  {formatCurrency(market.price)}
                </p>
              </div>

              {/* Market Data */}
              <div className="space-y-2 text-xs">
                {/* Time Remaining */}
                <div className="flex items-center justify-between">
                  <span className="text-text3">Time Left</span>
                  <span className="text-text font-mono">{formatTimeRemaining(market.time_remaining_sec)}</span>
                </div>

                {/* Spread */}
                <div className="flex items-center justify-between">
                  <span className="text-text3">Spread</span>
                  <span className="text-text font-mono">{market.spread.toFixed(3)}</span>
                </div>

                {/* Surebet */}
                {market.surebet_profitable && (
                  <div className="flex items-center justify-between p-2 rounded bg-success/10 border border-success/30">
                    <span className="text-success font-medium">SUREBET</span>
                    <span className="text-success font-mono font-bold">
                      +{market.surebet_profit_rate.toFixed(2)}%
                    </span>
                  </div>
                )}

                {/* Edge */}
                {!market.surebet_profitable && (market.edge_up > 0 || market.edge_down > 0) && (
                  <div className="flex items-center justify-between">
                    <span className="text-text3">Best Edge</span>
                    <span className="text-warning font-mono">
                      +{Math.max(market.edge_up, market.edge_down).toFixed(1)}%
                    </span>
                  </div>
                )}

                {/* Signal */}
                <div className={cn('flex items-center justify-between p-2 rounded', getSignalBg(market.signal))}>
                  <span className="text-xs font-medium">Signal</span>
                  <span className={cn('text-xs font-bold uppercase', getSignalColor(market.signal))}>
                    {market.signal}
                  </span>
                </div>
              </div>

              {/* Prices */}
              <div className="mt-3 pt-3 border-t border-border grid grid-cols-2 gap-2">
                <div className="text-center p-2 rounded bg-surface2">
                  <p className="text-text3 text-xs mb-1">UP</p>
                  <p className="text-success font-mono text-sm">{market.up_bid.toFixed(2)}</p>
                </div>
                <div className="text-center p-2 rounded bg-surface2">
                  <p className="text-text3 text-xs mb-1">DOWN</p>
                  <p className="text-error font-mono text-sm">{market.down_bid.toFixed(2)}</p>
                </div>
              </div>
            </div>

            {/* Decorative corner */}
            <div className="absolute bottom-0 right-0 w-16 h-16 bg-gradient-to-tl from-primary/5 to-transparent" />
          </motion.div>
        )
      })}
    </div>
  )
}

export default MarketGrid
