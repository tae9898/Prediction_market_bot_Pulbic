import { clsx, type ClassValue } from 'clsx'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export function formatCurrency(value: number, decimals = 2): string {
  if (value === 0) return '0.00'
  if (Math.abs(value) < 0.01) return value.toFixed(4)
  if (Math.abs(value) >= 1000000) return `${(value / 1000000).toFixed(2)}M`
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(2)}K`
  return value.toFixed(decimals)
}

export function formatPercentage(value: number, decimals = 2): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}

export function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp * 1000)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return 'Just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatTimeRemaining(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`
}

export function truncateAddress(address: string, length = 6): string {
  if (!address) return ''
  return `${address.slice(0, length)}...${address.slice(-length)}`
}

export function getSignalColor(signal: string): string {
  switch (signal.toUpperCase()) {
    case 'LONG':
    case 'SUREBET':
    case 'ENTRY':
      return 'text-primary'
    case 'SHORT':
    case 'EXIT':
      return 'text-accent'
    case 'WAITING':
    default:
      return 'text-text3'
  }
}

export function getSignalBg(signal: string): string {
  switch (signal.toUpperCase()) {
    case 'LONG':
    case 'SUREBET':
    case 'ENTRY':
      return 'signal-long'
    case 'SHORT':
    case 'EXIT':
      return 'signal-short'
    case 'WAITING':
    default:
      return 'signal-waiting'
  }
}
