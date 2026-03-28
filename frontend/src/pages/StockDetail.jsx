import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, TrendingUp, TrendingDown, Info, ShieldCheck, BarChart2 } from 'lucide-react';
import { getSymbolDetail } from '../lib/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

const StatCard = ({ label, value, subValue, color }) => (
  <div className="glass p-6 rounded-2xl border border-white/5 space-y-2 group hover:border-white/10 transition-colors">
    <span className="text-[10px] font-black uppercase text-gray-500 tracking-widest">{label}</span>
    <div className={cn("text-3xl font-black", color)}>{value}</div>
    <div className="text-[10px] text-gray-600 font-bold uppercase tracking-tighter">{subValue}</div>
  </div>
);

const StockDetail = () => {
  const { symbol } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDetail = async () => {
      try {
        const result = await getSymbolDetail(symbol);
        setData(result);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [symbol]);

  if (loading) return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-buy/10 border-t-buy rounded-full animate-spin" />
    </div>
  );

  if (!data) return (
    <div className="min-h-screen bg-background p-8 flex flex-col items-center justify-center text-center">
      <div className="text-gray-700 mb-6 font-black uppercase tracking-[0.2em]">Alpha Node Offline: {symbol}</div>
      <button 
        onClick={() => navigate('/')} 
        className="px-6 py-3 bg-buy text-black font-black rounded-xl flex items-center gap-2 hover:scale-105 transition-transform"
      >
        <ArrowLeft size={16} /> RETURN TO TERMINAL
      </button>
    </div>
  );

  return (
    <div className="min-h-screen bg-background text-gray-300 pb-20 overflow-x-hidden">
      <div className="max-w-[1200px] mx-auto p-8 pt-12">
        {/* Navigation */}
        <button 
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-gray-600 hover:text-white transition-colors text-[10px] font-black uppercase tracking-widest mb-12 group"
        >
          <div className="bg-white/5 p-1.5 rounded group-hover:bg-buy/10 group-hover:text-buy transition-all">
            <ArrowLeft size={14} />
          </div>
          Back to Screener
        </button>

        {/* Top Section */}
        <div className="flex flex-col lg:flex-row justify-between items-start gap-12 mb-20">
          <div className="space-y-6">
            <div className="flex items-center gap-4">
              <h1 className="text-7xl font-black text-white tracking-tighter">{symbol}</h1>
              <div className="px-3 py-1 bg-white/5 border border-white/10 rounded font-black text-[10px] text-gray-500 uppercase tracking-widest">
                NS: {symbol}
              </div>
            </div>
            <div className="flex items-center gap-8">
              <div className="text-5xl font-black text-white tabular-nums">
                ₹{data.price?.toLocaleString('en-IN') || "---"}
              </div>
              <div className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-black text-xs uppercase border",
                (data.change || 0) >= 0 ? "text-buy border-buy/20 bg-buy/5" : "text-sell border-sell/20 bg-sell/5"
              )}>
                {(data.change || 0) >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {data.change_percent || "0.00"}%
              </div>
            </div>
          </div>

          <div className="glass p-8 rounded-3xl border border-white/5 flex-1 max-w-2xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity pointer-events-none">
              <Info size={100} />
            </div>
            <div className="flex items-center gap-2 text-buy mb-4">
              <Info size={18} />
              <span className="text-[10px] font-black uppercase tracking-[0.2em]">Alpha Reasoning Node</span>
            </div>
            <p className="text-lg font-bold text-gray-400 leading-relaxed italic border-l-2 border-buy/30 pl-6 py-2">
              "{data.remarks || "No active reasoning logs available for this instrument. Monitoring patterns for session alpha."}"
            </p>
          </div>
        </div>

        {/* Middle Section: The Backtest Proof */}
        <div className="mb-20">
          <div className="flex items-center gap-4 mb-10">
            <div className="p-3 rounded-xl bg-buy/10 text-buy border border-buy/10 shadow-[0_0_20px_rgba(34,197,94,0.1)]">
              <ShieldCheck size={28} />
            </div>
            <div>
              <h2 className="text-3xl font-black text-white tracking-tighter uppercase tracking-widest">The Backtest <span className="text-buy">Proof</span></h2>
              <p className="text-[10px] text-gray-600 font-black uppercase tracking-[0.3em] mt-1">Validated across 12-month market regimes</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <StatCard 
              label="5-Day Accuracy" 
              value={`${data.win_rate_5d || "0"}%`} 
              subValue={<>Sharpe: <span className="text-white">{data.sharpe_5d || "0.00"}</span></>}
              color="text-white"
            />
            <StatCard 
              label="10-Day Accuracy" 
              value={`${data.win_rate_10d || "0"}%`} 
              subValue={<>Sharpe: <span className="text-white">{data.sharpe_10d || "0.00"}</span></>}
              color="text-buy"
            />
            <StatCard 
              label="30-Day Accuracy" 
              value={`${data.win_rate_30d || "0"}%`} 
              subValue={<>Sharpe: <span className="text-white">{data.sharpe_30d || "0.00"}</span></>}
              color="text-white"
            />
          </div>
        </div>

        {/* Bottom Section: Chart */}
        <div>
          <div className="flex items-center gap-4 mb-10">
            <div className="p-3 rounded-xl bg-white/5 text-gray-500 border border-white/5">
              <BarChart2 size={28} />
            </div>
            <div>
              <h2 className="text-3xl font-black text-white tracking-tighter uppercase tracking-widest">Trend <span className="text-gray-600">Dynamics</span></h2>
              <p className="text-[10px] text-gray-600 font-black uppercase tracking-[0.2em] mt-1">Live price action analysis</p>
            </div>
          </div>
          
          <div className="glass p-10 rounded-[32px] border border-white/5 h-[500px] shadow-inner relative">
            <div className="absolute inset-0 bg-gradient-to-b from-buy/[0.02] to-transparent pointer-events-none rounded-[32px]" />
            {data.chart_data && data.chart_data.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.chart_data}>
                  <defs>
                    <linearGradient id="lineGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.1}/>
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="5 5" vertical={false} stroke="#ffffff03" />
                  <XAxis 
                    dataKey="time" 
                    stroke="#374151" 
                    fontSize={11} 
                    tickLine={false} 
                    axisLine={false}
                    tick={{ fill: '#374151', fontWeight: '800' }}
                    dy={15}
                  />
                  <YAxis 
                    domain={['auto', 'auto']} 
                    stroke="#374151" 
                    fontSize={11} 
                    tickLine={false} 
                    axisLine={false}
                    tick={{ fill: '#374151', fontWeight: '800' }}
                    tickFormatter={(val) => `₹${val.toLocaleString('en-IN')}`}
                    dx={-15}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#171717', 
                      border: '1px solid rgba(255,255,255,0.05)', 
                      borderRadius: '16px', 
                      fontSize: '11px',
                      fontWeight: '800',
                      boxShadow: '0 10px 30px rgba(0,0,0,0.5)'
                    }}
                    itemStyle={{ color: '#22c55e' }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="price" 
                    stroke="#22c55e" 
                    strokeWidth={4} 
                    dot={false}
                    activeDot={{ r: 6, fill: '#22c55e', stroke: '#0a0a0a', strokeWidth: 2 }}
                    animationDuration={2500}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center opacity-20">
                <BarChart2 size={64} className="mb-4" />
                <p className="text-xs font-black uppercase tracking-[0.5em]">Chart Feed Terminated</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default StockDetail;
