import { motion } from 'framer-motion'
import { Home } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { cn } from '@/utils/cn'

export function NotFound() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <h1 className="text-text font-display font-bold text-6xl mb-4">404</h1>
        <p className="text-text3 text-xl mb-8">Page not found</p>
        <button
          onClick={() => navigate('/')}
          className={cn(
            'flex items-center gap-2 px-6 py-3 rounded-lg',
            'bg-primary/10 text-primary border border-primary/30',
            'hover:bg-primary/20 transition-all duration-200'
          )}
        >
          <Home size={18} />
          <span className="font-medium">Return Home</span>
        </button>
      </motion.div>
    </div>
  )
}

export default NotFound
