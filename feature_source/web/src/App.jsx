import React, { useState, useEffect } from 'react';
import { Activity, TrendingUp, TrendingDown, DollarSign, RefreshCw, Zap, PauseCircle, PlayCircle, PieChart, LayoutDashboard } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const API_BASE = "/api";

// Helper components
const Card = ({ title, children, className = "" }) => (
  <div className={`bg-gray-800 rounded-lg border border-gray-700 overflow-hidden ${className}`}>
    <div className="px-4 py-2 bg-gray-900 border-b border-gray-700 font-bold text-gray-300 flex justify-between items-center">
      {title}
    </div>
    <div className="p-4">
      {children}
    </div>
  </div>
);

const ValueLabel = ({ label, value, subValue, color = "white" }) => (
  <div className="flex flex-col">
    <span className="text-xs text-gray-400">{label}</span>
    <span className={`text-lg font-mono font-bold text-${color}-400`}>{value}</span>
    {subValue && <span className="text-xs text-gray-500">{subValue}</span>}
  </div>
);

const ProgressBar = ({ value, max = 100, color = "blue", label, subLabel }) => {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100);
  return (
    <div className="w-full mb-2">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-400">{label}</span>
        <span className="text-gray-300 font-mono">{subLabel}</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-2.5">
        <div className={`bg-${color}-500 h-2.5 rounded-full`} style={{ width: `${pct}%` }}></div>
      </div>
    </div>
  );
};

function App() {
  const [state, setState] = useState(null);
  const [history, setHistory] = useState([]);
  const [positions, setPositions] = useState([]);
  const [wallets, setWallets] = useState([]); // New state for wallets
  const [activeTab, setActiveTab] = useState("dashboard"); // dashboard, portfolio
  const [historyPeriod, setHistoryPeriod] = useState("all"); // 1d, 7d, all
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchState = async () => {
    try {
      const res = await fetch(`${API_BASE}/state`);
      if (!res.ok) throw new Error("Failed to fetch state");
      const data = await res.json();
      setState(data);
      setError(null);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchWallets = async () => {
    try {
      const res = await fetch(`${API_BASE}/wallets`);
      if (!res.ok) return;
      const data = await res.json();
      setWallets(data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/history?period=${historyPeriod}`);
      if (!res.ok) return;
      const data = await res.json();
      setHistory(data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchPositions = async () => {
    try {
      const res = await fetch(`${API_BASE}/portfolio/positions`);
      if (!res.ok) return;
      const data = await res.json();
      setPositions(data);
    } catch (err) {
      console.error(err);
    }
  };

  const toggleAutoTrade = async () => {
    try {
      await fetch(`${API_BASE}/toggle_auto`, { method: "POST" });
      fetchState();
    } catch (err) {
      console.error(err);
    }
  };

  const handleRefresh = () => {
      fetchState();
      fetchWallets();
      fetchHistory();
      fetchPositions();
  };

  useEffect(() => {
    fetchState();
    fetchWallets();
    fetchHistory();
    fetchPositions();
    const interval = setInterval(() => {
      fetchState();
      if (activeTab === 'portfolio') {
          fetchWallets();
          fetchHistory();
          fetchPositions();
      }
    }, 600000); // 10 minutes
    return () => clearInterval(interval);
  }, [activeTab, historyPeriod]);

  if (loading && !state) return <div className="p-8 text-center text-gray-400">Loading Dashboard...</div>;
  if (error && !state) return <div className="p-8 text-center text-red-500">Error: {error}</div>;

  const { state: botState, config } = state;
  // Use global total if available, else fallback to main bot's value
  const totalEquity = botState.global_portfolio_value || botState.portfolio_value;
  
  const assets = botState.assets || {};
  const assetKeys = Object.keys(assets);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-4 md:p-8 font-sans">
      {/* Header */}
      <header className="flex flex-col md:flex-row justify-between items-center mb-6 pb-4 border-b border-gray-800">
        <div className="flex items-center gap-3 mb-4 md:mb-0">
          <Zap className="text-yellow-400 w-8 h-8" />
          <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
            BTC Polymarket ARB Bot
          </h1>
        </div>
        
        <div className="flex gap-6 items-center">
            <div className="text-xs text-gray-500 italic mr-2 hidden lg:block">
                (Updates every 10 mins)
            </div>
            
            <button 
                onClick={handleRefresh}
                className="p-2 rounded-full bg-gray-800 text-cyan-400 hover:bg-gray-700 transition-colors"
                title="Refresh Data"
            >
                <RefreshCw size={18} />
            </button>

            {/* Tabs */}
            <div className="flex bg-gray-900 rounded-lg p-1 border border-gray-800 mr-4">
                <button 
                    onClick={() => setActiveTab('dashboard')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-md transition-all ${activeTab === 'dashboard' ? 'bg-gray-800 text-cyan-400 font-bold shadow-sm' : 'text-gray-400 hover:text-gray-200'}`}
                >
                    <LayoutDashboard size={18} /> Dashboard
                </button>
                <button 
                    onClick={() => setActiveTab('portfolio')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-md transition-all ${activeTab === 'portfolio' ? 'bg-gray-800 text-cyan-400 font-bold shadow-sm' : 'text-gray-400 hover:text-gray-200'}`}
                >
                    <PieChart size={18} /> Portfolio
                </button>
            </div>

            <div className="flex gap-4 border-r border-gray-800 pr-6 mr-2 hidden md:flex">
                <div className="text-right">
                    <div className="text-[10px] text-gray-500 uppercase tracking-wider">Total Profit</div>
                    <div className={`text-lg font-mono font-bold ${botState.global_total_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {botState.global_total_pnl >= 0 ? "+" : ""}${botState.global_total_pnl?.toLocaleString(undefined, {minimumFractionDigits: 2})}
                    </div>
                </div>
                <div className="text-right">
                    <div className="text-[10px] text-gray-500 uppercase tracking-wider">Total Equity</div>
                    <div className="text-lg font-mono font-bold text-cyan-400">
                        ${totalEquity?.toLocaleString(undefined, {minimumFractionDigits: 2})}
                    </div>
                </div>
            </div>
            
            <div 
                className={`flex items-center gap-2 px-4 py-2 rounded-full font-bold ${
                    botState.auto_trade 
                    ? "bg-green-600/80 text-white" 
                    : "bg-red-900/50 text-red-200 border border-red-800"
                }`}
            >
                {botState.auto_trade ? <PauseCircle size={18}/> : <PlayCircle size={18}/>}
                {botState.auto_trade ? "AUTO ON" : "AUTO OFF"}
            </div>
        </div>
      </header>

      {/* DASHBOARD TAB */}
      {activeTab === 'dashboard' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-6">
            {assetKeys.map(assetKey => {
                const asset = assets[assetKey];
                return (
                    <div key={assetKey} className="space-y-4">
                        <h2 className="text-xl font-bold text-cyan-500 flex items-center gap-2">
                            <Activity size={20}/> {assetKey} Market
                        </h2>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <Card title="Binance Spot">
                                <div className="flex justify-between items-end mb-4">
                                    <span className="text-2xl font-mono font-bold">${asset.price?.toLocaleString()}</span>
                                    <span className={`font-mono ${asset.change_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                                        {asset.change_pct >= 0 ? "+" : ""}{asset.change_pct?.toFixed(2)}%
                                    </span>
                                </div>
                                <div className="grid grid-cols-2 gap-4 mb-4">
                                    <ValueLabel label="24h Change" value={`$${asset.change_24h?.toFixed(2)}`} />
                                    <ValueLabel label="Volatility" value={`${(asset.volatility * 100)?.toFixed(1)}%`} color="purple"/>
                                </div>
                                <div className="text-center p-1 rounded bg-gray-900/50 text-xs font-bold tracking-wider">
                                    {asset.momentum} MOMENTUM
                                </div>
                            </Card>

                            <Card title="Polymarket">
                                <div className="flex justify-between mb-2">
                                    <span className="text-yellow-400 font-bold">Strike: ${asset.strike_price?.toLocaleString()}</span>
                                    <span className="text-gray-400 text-sm">⏱ {asset.time_remaining}</span>
                                </div>
                                
                                <div className="space-y-3 mt-4">
                                    <div className="flex justify-between items-center p-2 rounded bg-green-900/20 border border-green-900/50">
                                        <span className="font-bold text-green-400 flex items-center gap-1"><TrendingUp size={16}/> UP</span>
                                        <div className="text-right">
                                            <div className="text-sm font-mono">Ask: {(asset.up_ask * 100).toFixed(1)}%</div>
                                            <div className="text-xs text-gray-500">Bid: {(asset.up_bid * 100).toFixed(1)}%</div>
                                        </div>
                                    </div>
                                    <div className="flex justify-between items-center p-2 rounded bg-red-900/20 border border-red-900/50">
                                        <span className="font-bold text-red-400 flex items-center gap-1"><TrendingDown size={16}/> DOWN</span>
                                        <div className="text-right">
                                            <div className="text-sm font-mono">Ask: {(asset.down_ask * 100).toFixed(1)}%</div>
                                            <div className="text-xs text-gray-500">Bid: {(asset.down_bid * 100).toFixed(1)}%</div>
                                        </div>
                                    </div>
                                </div>
                            </Card>
                        </div>

                        <Card title="Fair Value Model">
                            <div className="space-y-6">
                                <div>
                                    <ProgressBar 
                                        value={asset.fair_up * 100} 
                                        max={100} 
                                        color="cyan" 
                                        label="FAIR (UP)" 
                                        subLabel={`${(asset.fair_up * 100).toFixed(1)}%`}
                                    />
                                    <ProgressBar 
                                        value={asset.up_ask * 100} 
                                        max={100} 
                                        color="yellow" 
                                        label="MARKET (UP)" 
                                        subLabel={`${(asset.up_ask * 100).toFixed(1)}%`}
                                    />
                                    <div className="flex justify-end text-sm mt-1">
                                        <span className="text-gray-500 mr-2">Edge:</span>
                                        <span className={asset.edge_up > 0 ? "text-green-400 font-bold" : "text-red-400"}>
                                            {asset.edge_up > 0 ? "+" : ""}{asset.edge_up.toFixed(2)}%
                                        </span>
                                    </div>
                                </div>

                                <div>
                                    <ProgressBar 
                                        value={asset.fair_down * 100} 
                                        max={100} 
                                        color="cyan" 
                                        label="FAIR (DOWN)" 
                                        subLabel={`${(asset.fair_down * 100).toFixed(1)}%`}
                                    />
                                    <ProgressBar 
                                        value={asset.down_ask * 100} 
                                        max={100} 
                                        color="yellow" 
                                        label="MARKET (DOWN)" 
                                        subLabel={`${(asset.down_ask * 100).toFixed(1)}%`}
                                    />
                                    <div className="flex justify-end text-sm mt-1">
                                        <span className="text-gray-500 mr-2">Edge:</span>
                                        <span className={asset.edge_down > 0 ? "text-green-400 font-bold" : "text-red-400"}>
                                            {asset.edge_down > 0 ? "+" : ""}{asset.edge_down.toFixed(2)}%
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </Card>

                        {asset.has_position && (
                            <Card title="Active Position" className="border-yellow-600/50">
                                <div className="flex items-center gap-4">
                                    <div className={`p-3 rounded-full ${asset.position_direction === 'UP' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                        {asset.position_direction === 'UP' ? <TrendingUp size={24}/> : <TrendingDown size={24}/>}
                                    </div>
                                    <div className="flex-1">
                                        <div className="text-sm text-gray-400">Direction</div>
                                        <div className="font-bold text-xl">{asset.position_direction}</div>
                                    </div>
                                    <div className="flex-1 text-right">
                                        <div className="text-sm text-gray-400">PnL</div>
                                        <div className={`font-mono text-xl font-bold ${asset.position_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                                            {asset.position_pnl >= 0 ? "+" : ""}${asset.position_pnl.toFixed(2)}
                                        </div>
                                    </div>
                                </div>
                                <div className="grid grid-cols-3 gap-2 mt-4 text-sm text-gray-400">
                                    <div>Size: {asset.position_size.toFixed(1)}</div>
                                    <div>Avg: ${asset.position_avg_price.toFixed(3)}</div>
                                    <div>Cost: ${asset.position_cost.toFixed(2)}</div>
                                </div>
                            </Card>
                        )}
                    </div>
                );
            })}
        </div>
      )}

      {/* PORTFOLIO TAB */}
      {activeTab === 'portfolio' && (
        <div className="space-y-6">
            <Card title="Connected Wallets">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left text-gray-400">
                        <thead className="text-xs text-gray-500 uppercase bg-gray-900/50">
                            <tr>
                                <th className="px-4 py-3">ID</th>
                                <th className="px-4 py-3">Address</th>
                                <th className="px-4 py-3 text-right">Cash (USDC)</th>
                                <th className="px-4 py-3 text-right">Equity</th>
                                <th className="px-4 py-3 text-right">Profit (PnL)</th>
                                <th className="px-4 py-3 text-center">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {wallets.map((wallet, idx) => (
                                <tr key={idx} className="border-b border-gray-800 hover:bg-gray-800/50">
                                    <td className="px-4 py-3 font-medium text-white">{wallet.id}</td>
                                    <td className="px-4 py-3 font-mono text-xs">
                                        {wallet.address ? `${wallet.address.substring(0, 6)}...${wallet.address.substring(38)}` : "Unknown"}
                                    </td>
                                    <td className="px-4 py-3 text-right text-gray-300 font-mono">
                                        ${wallet.balance?.toLocaleString(undefined, {minimumFractionDigits: 2})}
                                    </td>
                                    <td className="px-4 py-3 text-right text-cyan-400 font-bold font-mono">
                                        ${wallet.equity?.toLocaleString(undefined, {minimumFractionDigits: 2})}
                                    </td>
                                    <td className={`px-4 py-3 text-right font-bold font-mono ${wallet.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                                        {wallet.pnl >= 0 ? "+" : ""}${wallet.pnl?.toFixed(2)}
                                    </td>
                                    <td className="px-4 py-3 text-center">
                                        <span className={`px-2 py-1 rounded text-[10px] font-bold ${wallet.active ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
                                            {wallet.active ? 'ACTIVE' : 'STOPPED'}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </Card>

            <Card title="Main Wallet Info">
                <div className="flex justify-between items-center">
                    <div>
                        <div className="text-sm text-gray-400">Wallet Address</div>
                        <div className="font-mono text-lg text-yellow-400">{botState.wallet_address || "Loading..."}</div>
                    </div>
                    <div className="text-right">
                        <div className="text-sm text-gray-400">Current Balance</div>
                        <div className="font-mono text-2xl font-bold text-green-400">
                            ${botState.usdc_balance?.toLocaleString()} <span className="text-sm text-gray-500">USDC</span>
                        </div>
                    </div>
                </div>
            </Card>

            <div className="flex flex-col gap-6">
                <Card title="PnL History">
                    <div className="flex justify-end gap-2 mb-4">
                        {['1d', '7d', 'all'].map(p => (
                            <button
                                key={p}
                                onClick={() => setHistoryPeriod(p)}
                                className={`px-3 py-1 rounded text-sm font-bold ${historyPeriod === p ? 'bg-cyan-600 text-white' : 'bg-gray-700 text-gray-400'}`}
                            >
                                {p.toUpperCase()}
                            </button>
                        ))}
                    </div>
                    
                    <div className="h-64 w-full bg-gray-900/50 rounded-lg p-2">
                        {history.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={history}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                    <XAxis 
                                        dataKey="date_str" 
                                        stroke="#9CA3AF" 
                                        tick={{fontSize: 10}}
                                        tickFormatter={(val) => val.split(' ')[1].substring(0,5)} 
                                    />
                                    <YAxis 
                                        domain={['auto', 'auto']} 
                                        stroke="#9CA3AF"
                                        tick={{fontSize: 12}}
                                        tickFormatter={(val) => `$${val}`}
                                    />
                                    <Tooltip 
                                        contentStyle={{backgroundColor: '#1F2937', border: 'none'}}
                                        itemStyle={{color: '#E5E7EB'}}
                                    />
                                    <Line 
                                        type="monotone" 
                                        dataKey="total_value" 
                                        stroke="#22D3EE" 
                                        strokeWidth={2}
                                        dot={false}
                                        name="Total Value"
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex items-center justify-center h-full text-gray-500">
                                Not enough data yet. History recording started...
                            </div>
                        )}
                    </div>
                </Card>

                {/* Positions Table Removed
                <Card title="Current Positions">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm text-left text-gray-400">
                            <thead className="text-xs text-gray-500 uppercase bg-gray-900/50">
                                <tr>
                                    <th className="px-4 py-3">Market</th>
                                    <th className="px-4 py-3">Side</th>
                                    <th className="px-4 py-3 text-right">Size</th>
                                    <th className="px-4 py-3 text-right">Avg Price</th>
                                    <th className="px-4 py-3 text-right">PnL</th>
                                </tr>
                            </thead>
                            <tbody>
                                {positions.map((pos, idx) => (
                                    <tr key={idx} className="border-b border-gray-800 hover:bg-gray-800/50">
                                        <td className="px-4 py-3 font-medium text-white truncate max-w-[150px]" title={pos.market}>{pos.market}</td>
                                        <td className="px-4 py-3">
                                            <span className={`px-2 py-1 rounded text-xs font-bold ${pos.side === 'UP' || pos.side === 'YES' ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
                                                {pos.side}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-right font-mono">{pos.size.toFixed(2)}</td>
                                        <td className="px-4 py-3 text-right font-mono">${pos.avg_price.toFixed(3)}</td>
                                        <td className={`px-4 py-3 text-right font-mono font-bold ${pos.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {pos.pnl >= 0 ? '+' : ''}{pos.pnl.toFixed(2)} ({pos.pnl_pct.toFixed(1)}%)
                                        </td>
                                    </tr>
                                ))}
                                {positions.length === 0 && (
                                    <tr>
                                        <td colSpan="5" className="px-4 py-8 text-center text-gray-500">
                                            No active positions found.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </Card>
                */}
            </div>
        </div>
      )}
      
      {/* Logs Section */}
      <Card title="System Logs">
        <div className="h-48 overflow-y-auto font-mono text-xs text-gray-400 space-y-1 p-2 bg-black rounded">
            {[...(botState.logs || [])].reverse().map((log, i) => {
                let strategyType = '';
                const strategyMatch = log.match(/Trend (Entry|Exit) \((directional|contrarian)\)/);
                if (strategyMatch) {
                    strategyType = strategyMatch[2];
                }

                const emojiMap = {
                    'directional': '📊',
                    'contrarian': '🔄'
                };

                let displayLog = log;
                if (strategyType) {
                    const emoji = emojiMap[strategyType] || '';
                    displayLog = log.replace(/Trend (Entry|Exit) \((directional|contrarian)\)/, `Trend $1 (${strategyType})`);
                }

                return (
                    <div key={i} className="border-b border-gray-900 pb-0.5 flex items-start gap-2">
                        {strategyType && (
                            <span className="text-yellow-400">
                                {strategyType === 'directional' ? '📊' : '🔄'}
                            </span>
                        )}
                        <span className={strategyType ? '' : ''}>{displayLog}</span>
                    </div>
                );
            })}
        </div>
      </Card>
    </div>
  );
}

export default App;