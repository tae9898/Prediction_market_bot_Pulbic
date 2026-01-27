import { motion } from 'framer-motion'
import { Wallet, DollarSign, TrendingUp, Power } from 'lucide-react'
import { cn, formatCurrency, truncateAddress } from '@/utils/cn'
import type { WalletInfo } from '@/api/types'

interface WalletCardProps {
  wallet: WalletInfo
  onToggleAutoTrade?: (id: string) => void
  onClick?: () => void
  className?: string
}

export function WalletCard({ wallet, onToggleAutoTrade, onClick, className }: WalletCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className={cn(
        'group relative overflow-hidden rounded-xl border border-border bg-surface p-5',
        'hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5',
        'transition-all duration-300 cursor-pointer',
        !wallet.is_connected && 'opacity-60',
        className
      )}
    >
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

      {/* Connection indicator */}
      {wallet.is_connected && (
        <div className="absolute top-4 right-4">
          <div className="w-2 h-2 rounded-full bg-success animate-pulse shadow-lg shadow-success/50" />
        </div>
      )}

      <div className="relative">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2.5 rounded-lg bg-gradient-to-br from-primary/10 to-primary/5 border border-primary/20">
            <Wallet size={20} className="text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-text font-display font-semibold">Wallet {wallet.id}</p>
            <p className="text-text3 text-xs font-mono truncate">
              {truncateAddress(wallet.address)}
            </p>
          </div>
        </div>

        {/* Balance */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-text3">
              <DollarSign size={16} />
              <span className="text-sm">USDC Balance</span>
            </div>
            <p className="text-text font-mono font-semibold">
              {formatCurrency(wallet.usdc_balance)}
            </p>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-text3">
              <TrendingUp size={16} />
              <span className="text-sm">Portfolio Value</span>
            </div>
            <p className="text-primary font-mono font-display font-bold text-lg">
              {formatCurrency(wallet.portfolio_value)}
            </p>
          </div>

          {wallet.reserved_balance > 0 && (
            <div className="flex items-center justify-between text-text3 text-xs">
              <span>Reserved</span>
              <span className="font-mono">{formatCurrency(wallet.reserved_balance)}</span>
            </div>
          )}

          {/* Auto-trade toggle */}
          {onToggleAutoTrade && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onToggleAutoTrade(wallet.id)
              }}
              className={cn(
                'w-full mt-3 flex items-center justify-center gap-2 py-2 rounded-lg border transition-all duration-200',
                wallet.auto_trade
                  ? 'bg-success/10 border-success/30 text-success hover:bg-success/20'
                  : 'bg-surface2 border-border text-text3 hover:border-text3/50'
              )}
            >
              <Power size={16} strokeWidth={2} />
              <span className="text-sm font-medium">
                Auto-trade {wallet.auto_trade ? 'ON' : 'OFF'}
              </span>
            </button>
          )}
        </div>
      </div>

      {/* Decorative corner */}
      <div className="absolute bottom-0 right-0 w-20 h-20 bg-gradient-to-tl from-primary/5 to-transparent" />
    </motion.div>
  )
}

export default WalletCard
