import { useMemo } from 'react'
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  TooltipProps,
} from 'recharts'
import { formatCurrency, formatTimestamp } from '@/utils/cn'
import type { PortfolioSnapshot, PnLSnapshot } from '@/api/types'

interface PerformanceChartProps {
  data: PortfolioSnapshot[] | PnLSnapshot[]
  type?: 'portfolio' | 'pnl'
  className?: string
}

export function PerformanceChart({ data, type = 'portfolio', className }: PerformanceChartProps) {
  const chartData = useMemo(() => {
    if (type === 'portfolio') {
      return (data as PortfolioSnapshot[]).map((d) => ({
        time: formatTimestamp(d.timestamp),
        value: d.total_value,
        invested: d.invested_value,
        cash: d.usdc_balance,
      }))
    }
    return (data as PnLSnapshot[]).map((d) => ({
      time: formatTimestamp(d.timestamp),
      total: d.total_pnl,
      realized: d.realized_pnl,
      unrealized: d.unrealized_pnl,
    }))
  }, [data, type])

  const CustomTooltip = ({ active, payload }: TooltipProps<any, any>) => {
    if (!active || !payload?.length) return null

    return (
      <div className="bg-surface2 border border-border rounded-lg p-3 shadow-xl">
        <p className="text-text3 text-xs mb-2">{payload[0].payload.time}</p>
        {type === 'portfolio' ? (
          <>
            <p className="text-text text-sm">
              Total: <span className="font-mono font-semibold">{formatCurrency(payload[0].value)}</span>
            </p>
            <p className="text-primary text-xs">
              Invested: <span className="font-mono">{formatCurrency(payload[0].payload.invested)}</span>
            </p>
            <p className="text-text3 text-xs">
              Cash: <span className="font-mono">{formatCurrency(payload[0].payload.cash)}</span>
            </p>
          </>
        ) : (
          <>
            <p className="text-text text-sm">
              Total: <span className="font-mono font-semibold">{formatCurrency(payload[0].value)}</span>
            </p>
            <p className="text-success text-xs">
              Realized: <span className="font-mono">{formatCurrency(payload[0].payload.realized)}</span>
            </p>
            <p className="text-warning text-xs">
              Unrealized: <span className="font-mono">{formatCurrency(payload[0].payload.unrealized)}</span>
            </p>
          </>
        )}
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div className={cn('flex items-center justify-center h-64 text-text3 text-sm', className)}>
        No data available
      </div>
    )
  }

  const ChartComponent = type === 'portfolio' ? AreaChart : LineChart

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={300}>
        <ChartComponent data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#00ff9f" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#00ff9f" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#00ccff" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#00ccff" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" vertical={false} />
          <XAxis
            dataKey="time"
            stroke="#606070"
            fontSize={12}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            stroke="#606070"
            fontSize={12}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value) => (value >= 1000 ? `${(value / 1000).toFixed(0)}K` : value.toFixed(0))}
          />
          <Tooltip content={<CustomTooltip />} />
          {type === 'portfolio' ? (
            <Area
              type="monotone"
              dataKey="value"
              stroke="#00ff9f"
              strokeWidth={2}
              fill="url(#colorValue)"
            />
          ) : (
            <>
              <Line type="monotone" dataKey="total" stroke="#00ccff" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="realized" stroke="#00ff9f" strokeWidth={1} dot={false} strokeDasharray="5 5" />
              <Line type="monotone" dataKey="unrealized" stroke="#ffbe0b" strokeWidth={1} dot={false} strokeDasharray="5 5" />
            </>
          )}
        </ChartComponent>
      </ResponsiveContainer>
    </div>
  )
}

export default PerformanceChart
