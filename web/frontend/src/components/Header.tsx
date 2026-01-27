import { Activity, Zap, Wifi, WifiOff } from 'lucide-react'
import { cn } from '@/utils/cn'

interface HeaderProps {
  connected?: boolean
  className?: string
}

export function Header({ connected = true, className }: HeaderProps) {
  return (
    <header className={cn('border-b border-border bg-surface/50 backdrop-blur-xl sticky top-0 z-50', className)}>
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary2 flex items-center justify-center">
                <Activity size={20} className="text-background" strokeWidth={2.5} />
              </div>
              <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-success border-2 border-background" />
            </div>
            <div>
              <h1 className="text-text font-display font-bold text-xl tracking-tight">
                Trading Bot
              </h1>
              <p className="text-text3 text-xs">Real-time Dashboard</p>
            </div>
          </div>

          {/* Status */}
          <div className="flex items-center gap-4">
            <div className={cn('flex items-center gap-2 px-3 py-1.5 rounded-lg', connected ? 'bg-success/10' : 'bg-error/10')}>
              {connected ? (
                <Wifi size={16} className="text-success" />
              ) : (
                <WifiOff size={16} className="text-error" />
              )}
              <span className={cn('text-sm font-medium', connected ? 'text-success' : 'text-error')}>
                {connected ? 'Live' : 'Offline'}
              </span>
            </div>

            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary/10">
              <Zap size={16} className="text-primary" />
              <span className="text-primary text-sm font-medium">Active</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}

export default Header
