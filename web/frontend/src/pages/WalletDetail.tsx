import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, Wallet, TrendingUp, DollarSign, BarChart3, Settings } from 'lucide-react'
import { Header } from '@/components/Header'
import { StatusCard } from '@/components/StatusCard'
import { PositionTable } from '@/components/PositionTable'
import { PerformanceChart } from '@/components/PerformanceChart'
import { MarketGrid } from '@/components/MarketGrid'
import { useWallets } from '@/hooks/useWallets'
import { usePerformance } from '@/hooks/usePerformance'
import { useWebSocket } from '@/hooks/useWebSocket'
import { cn, formatCurrency } from '@/utils/cn'

export function WalletDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { wallets, loading, toggleAutoTrade } = useWallets()
  const { performance, portfolioHistory } = usePerformance(id)
  const { isConnected } = useWebSocket()

  const walletData = wallets?.find((w) => w.info.id === id)

  useEffect(() => {
    if (!loading && !walletData) {
      navigate('/')
    }
  }, [loading, walletData, navigate])

  if (loading || !walletData) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-text3">Loading wallet data...</div>
      </div>
    )
  }

  const wallet = walletData.info
  const positions = walletData.positions
  const markets = walletData.markets

  const totalPnL = positions.reduce((sum, p) => sum + p.pnl, 0)

  return (
    <div className="min-h-screen bg-background grid-pattern">
      <Header connected={isConnected} />

      <main className="container mx-auto px-4 py-8">
        {/* Back Button */}
        <motion.button
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          onClick={() => navigate('/')}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-lg mb-6',
            'bg-surface border border-border hover:border-primary/50',
            'text-text3 hover:text-primary transition-all duration-200'
          )}
        >
          <ArrowLeft size={18} />
          <span className="text-sm font-medium">Back to Dashboard</span>
        </motion.button>

        {/* Wallet Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-primary to-primary2 flex items-center justify-center">
                <Wallet size={32} className="text-background" />
              </div>
              <div>
                <h2 className="text-text font-display font-bold text-3xl mb-1">
                  Wallet {wallet.id}
                </h2>
                <p className="text-text3 font-mono text-sm">
                  {wallet.address}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-medium',
                wallet.is_connected ? 'bg-success/10 text-success' : 'bg-error/10 text-error'
              )}>
                {wallet.is_connected ? 'Connected' : 'Disconnected'}
              </div>
              <div className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-medium',
                wallet.auto_trade ? 'bg-primary/10 text-primary' : 'bg-surface2 text-text3'
              )}>
                Auto-trade {wallet.auto_trade ? 'ON' : 'OFF'}
              </div>
              <button
                onClick={() => toggleAutoTrade(wallet.id)}
                className={cn(
                  'px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200',
                  wallet.auto_trade
                    ? 'bg-error/10 text-error hover:bg-error/20'
                    : 'bg-success/10 text-success hover:bg-success/20'
                )}
              >
                {wallet.auto_trade ? 'Disable' : 'Enable'} Auto-trade
              </button>
            </div>
          </div>
        </motion.div>

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <StatusCard
            title="Portfolio Value"
            value={wallet.portfolio_value}
            icon={Wallet}
            trend={totalPnL >= 0 ? 'up' : 'down'}
            change={totalPnL}
          />
          <StatusCard
            title="USDC Balance"
            value={wallet.usdc_balance}
            icon={DollarSign}
          />
          <StatusCard
            title="Reserved"
            value={wallet.reserved_balance}
            icon={BarChart3}
          />
          <StatusCard
            title="Invested"
            value={wallet.portfolio_value - wallet.usdc_balance}
            icon={TrendingUp}
          />
        </div>

        {/* Performance Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-xl border border-border bg-surface p-6 mb-8"
        >
          <h3 className="text-text font-display font-semibold text-xl mb-4">Performance</h3>
          <PerformanceChart data={portfolioHistory} type="portfolio" />
        </motion.div>

        {/* Positions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mb-8"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-text font-display font-semibold text-xl">Open Positions</h3>
            <span className="text-text3 text-sm">{positions.length} positions</span>
          </div>
          <PositionTable positions={positions} />
        </motion.div>

        {/* Markets */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-text font-display font-semibold text-xl">Monitored Markets</h3>
            <span className="text-text3 text-sm">{markets.length} markets</span>
          </div>
          <MarketGrid markets={markets} />
        </motion.div>
      </main>
    </div>
  )
}

export default WalletDetail
