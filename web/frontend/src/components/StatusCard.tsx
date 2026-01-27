import { motion } from 'framer-motion'
import { LucideIcon } from 'lucide-react'
import { cn, formatCurrency, formatPercentage } from '@/utils/cn'

interface StatusCardProps {
  title: string
  value: string | number
  change?: number
  icon: LucideIcon
  trend?: 'up' | 'down' | 'neutral'
  size?: 'sm' | 'md' | 'lg'
  className?: string
  glow?: boolean
}

export function StatusCard({
  title,
  value,
  change,
  icon: Icon,
  trend,
  size = 'md',
  className,
  glow = false,
}: StatusCardProps) {
  const sizeClasses = {
    sm: 'p-4',
    md: 'p-5',
    lg: 'p-6',
  }

  const iconSizes = {
    sm: 16,
    md: 20,
    lg: 24,
  }

  const trendColor = trend === 'up' ? 'text-success' : trend === 'down' ? 'text-error' : 'text-text3'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        'relative overflow-hidden rounded-xl border border-border bg-surface',
        'hover:border-primary/50 transition-all duration-300',
        glow && 'hover:shadow-lg hover:shadow-primary/10',
        sizeClasses[size],
        className
      )}
    >
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 hover:opacity-100 transition-opacity duration-300" />

      <div className="relative flex items-start justify-between">
        <div className="flex-1">
          <p className="text-text3 text-sm font-medium mb-1">{title}</p>
          <p className="text-text font-display font-bold text-2xl tracking-tight">
            {typeof value === 'number' ? formatCurrency(value) : value}
          </p>
          {change !== undefined && (
            <p className={cn('text-sm font-mono mt-1', trendColor)}>
              {formatPercentage(change)}
            </p>
          )}
        </div>

        <div
          className={cn(
            'rounded-lg p-2.5',
            'bg-gradient-to-br from-primary/10 to-primary/5',
            'border border-primary/20'
          )}
        >
          <Icon size={iconSizes[size]} className="text-primary" strokeWidth={2} />
        </div>
      </div>

      {/* Decorative corner */}
      <div className="absolute bottom-0 right-0 w-16 h-16 bg-gradient-to-tl from-primary/5 to-transparent" />
    </motion.div>
  )
}

export default StatusCard
