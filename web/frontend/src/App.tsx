import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Dashboard } from '@/pages/Dashboard'
import { WalletDetail } from '@/pages/WalletDetail'
import { NotFound } from '@/pages/NotFound'
import { useWebSocket } from '@/hooks/useWebSocket'

function App() {
  // Global WebSocket connection for real-time updates
  useWebSocket({
    onConnect: () => {
      console.log('Connected to trading bot WebSocket')
    },
    onDisconnect: () => {
      console.log('Disconnected from trading bot WebSocket')
    },
    onMessage: (message) => {
      console.log('WebSocket message:', message.type)
    },
  })

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/wallet/:id" element={<WalletDetail />} />
        <Route path="/404" element={<NotFound />} />
        <Route path="*" element={<Navigate to="/404" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
