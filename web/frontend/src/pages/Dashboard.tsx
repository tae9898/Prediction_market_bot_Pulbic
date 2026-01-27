import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Wallet, TrendingUp, DollarSign, Activity, BarChart3 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Header } from '@/components/Header'
import { StatusCard } from '@/components/StatusCard'
import { WalletCard } from '@/components/WalletCard'
import { PositionTable } from '@/components/PositionTable'
import { PerformanceChart } from '@/components/PerformanceChart'
import { SignalList } from '@/components/SignalList'
import { MarketGrid } from '@/components/MarketGrid'
import { useStatus } from '@/hooks/useStatus'
import { useWallets } from '@/hooks/useWallets'
import { usePerformance } from '@/hooks/usePerformance'
import { useSignals } from '@/hooks/useSignals'
import { useWebSocket } from '@/hooks/useWebSocket'
import { formatCurrency } from '@/utils/cn'

export function Dashboard() {
  const navigate = useNavigate()
  const { status, loading: statusLoading } = useStatus()
  const { wallets, loading: walletsLoading, toggleAutoTrade } = useWallets()
  const { performance, portfolioHistory } = usePerformance()
  const { signals } = useSignals()
  const { isConnected } = useWebSocket({
    onStateUpdate: (state) => {
      // Real-time state updates
      console.log('State update:', state)
    },
  })

  // Calculate total PnL from all positions
  const totalPnL = wallets?.reduce((sum, w) => {
    return sum + w.positions.reduce((pSum, p) => pSum + p.pnl, 0)
  }, 0) || 0

  // Get all positions across wallets
  const allPositions = wallets?.flatMap((w) => w.positions) || []

  // Get markets from first wallet
  const markets = wallets?.[0]?.markets || []

  return (
    <div className="min-h-screen bg-background grid-pattern">
      <Header connected={isConnected} />

      <main className="container mx-auto px-4 py-8">
        {/* Page Title */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h2 className="text-text font-display font-bold text-3xl mb-2">Dashboard</h2>
          <p className="text-text3">
            Real-time overview of your trading bot performance
          </p>
        </motion.div>

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatusCard
            title="Total Portfolio"
            value={status?.total_portfolio_value || 0}
            icon={Wallet}
            trend={totalPnL >= 0 ? 'up' : 'down'}
            change={totalPnL}
            glow
          />
          <StatusCard
            title="Available USDC"
            value={status?.total_usdc || 0}
            icon={DollarSign}
          />
          <StatusCard
            title="Total Invested"
            value={status?.total_invested || 0}
            icon={TrendingUp}
          />
          <StatusCard
            title="Total PnL"
            value={status?.total_pnl || 0}
            icon={BarChart3}
            trend={status?.total_pnl >= 0 ? 'up' : 'down'}
          />
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Left Column - Wallets & Positions */}
          <div className="lg:col-span-2 space-y-6">
            {/* Wallets */}
            <section>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-text font-display font-semibold text-lg">Wallets</h3>
                <span className="text-text3 text-sm">{wallets?.length || 0} wallets</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {walletsLoading ? (
                  [...Array(2)].map((_, i) => (
                    <div key={i} className="h-40 rounded-xl bg-surface animate-pulse" />
                  ))
                ) : (
                  wallets?.map((wallet) => (
                    <WalletCard
                      key={wallet.info.id}
                      wallet={wallet.info}
                      onToggleAutoTrade={toggleAutoTrade}
                      onClick={() => navigate(`/wallet/${wallet.info.id}`)}
                    />
                  ))
                )}
              </div>
            </section>

            {/* Positions */}
            <section>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-text font-display font-semibold text-lg">Open Positions</h3>
                <span className="text-text3 text-sm">{allPositions.length} positions</span>
              </div>
              <PositionTable positions={allPositions} loading={walletsLoading} />
            </section>
          </div>

          {/* Right Column - Performance & Signals */}
          <div className="space-y-6">
            {/* Portfolio Chart */}
            <section className="rounded-xl border border-border bg-surface p-5">
              <h3 className="text-text font-display font-semibold text-lg mb-4">Portfolio Value</h3>
              <PerformanceChart data={portfolioHistory} type="portfolio" />
            </section>

            {/* Recent Signals */}
            <section className="rounded-xl border border-border bg-surface p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-text font-display font-semibold text-lg">Recent Signals</h3>
                <span className="text-text3 text-sm">Last 10</span>
              </div>
              <SignalList signals={signals} />
            </section>
          </div>
        </div>

        {/* Markets */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-text font-display font-semibold text-lg">Market Overview</h3>
            <span className="text-text3 text-sm">{markets.length} markets</span>
          </div>
          <MarketGrid markets={markets} loading={walletsLoading} />
        </section>
      </main>
    </div>
  )
}

export default Dashboard
