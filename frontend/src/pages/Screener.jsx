import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { TrendingUp, TrendingDown, Search, BarChart3, Filter } from 'lucide-react';
import { getStocks } from '../lib/api';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

const SignalBadge = ({ signal }) => {
  const isBuy = signal === 'BUY';
  const isSell = signal === 'SELL';
  
  return (
    <div className={cn(
      "px-3 py-1 rounded-full text-[10px] font-black uppercase flex items-center gap-1.5 w-fit",
      isBuy ? "bg-buy/20 text-buy border border-buy/30 shadow-[0_0_10px_rgba(34,197,94,0.1)]" : 
      isSell ? "bg-sell/20 text-sell border border-sell/30 shadow-[0_0_10px_rgba(239,68,68,0.1)]" : 
      "bg-gray-800/50 text-gray-500 border border-gray-700/50"
    )}>
      {isBuy && <TrendingUp size={12} />}
      {isSell && <TrendingDown size={12} />}
      {signal}
    </div>
  );
};

const ConfidenceBar = ({ value }) => (
  <div className="w-full bg-white/5 h-1 rounded-full overflow-hidden">
    <div 
      className={cn(
        "h-full rounded-full transition-all duration-1000",
        value > 70 ? "bg-buy" : value > 40 ? "bg-yellow-500" : "bg-sell"
      )}
      style={{ width: `${value}%` }}
    />
  </div>
);

const Screener = () => {
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchStocks = async () => {
      try {
        const data = await getStocks();
        // Assuming backend returns an array of stock objects
        // If data is empty, set some dummy data for preview
        setStocks(data || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchStocks();
  }, []);

  const filteredStocks = stocks.filter(s => 
    s.symbol.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-background text-gray-300">
      <div className="max-w-[1600px] mx-auto p-8 pt-12">
        <header className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 mb-12">
          <div>
            <div className="flex items-center gap-2 text-buy mb-2">
              <BarChart3 size={20} />
              <span className="text-xs font-black uppercase tracking-[0.2em]">Alpha Terminal v1.0</span>
            </div>
            <h1 className="text-5xl font-black text-white tracking-tighter mb-4">
              NSE Pattern <span className="text-buy">Intel</span>
            </h1>
            <p className="text-gray-500 max-w-xl font-medium">
              Multi-agent technical scanner evaluating Nifty 50 stocks against 12+ quantitative patterns and historical market regimes.
            </p>
          </div>
          
          <div className="flex items-center gap-4 w-full md:w-auto">
            <div className="relative flex-1 md:w-80">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-600" size={18} />
              <input 
                type="text" 
                placeholder="Search ticker..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-card border border-white/5 rounded-xl py-3 pl-12 pr-4 focus:outline-none focus:ring-2 focus:ring-buy/20 transition-all font-sans text-sm placeholder:text-gray-700"
              />
            </div>
            <button className="bg-white/5 p-3 rounded-xl border border-white/5 text-gray-400 hover:text-white hover:bg-white/10 transition-all">
              <Filter size={20} />
            </button>
          </div>
        </header>

        <main className="glass border border-white/5 rounded-2xl overflow-hidden shadow-2xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-white/[0.02] border-b border-white/5 text-[11px] font-black uppercase tracking-widest text-gray-500">
                  <th className="px-8 py-5">Instrument</th>
                  <th className="px-8 py-5">Signal</th>
                  <th className="px-8 py-5 w-48">Confidence</th>
                  <th className="px-8 py-5">Detected Pattern</th>
                  <th className="px-8 py-5 text-right">Success Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.02]">
                {loading ? (
                  Array(10).fill(0).map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      <td className="px-8 py-6"><div className="h-5 bg-white/5 rounded w-32"></div></td>
                      <td className="px-8 py-6"><div className="h-7 bg-white/5 rounded-full w-20"></div></td>
                      <td className="px-8 py-6"><div className="h-1 bg-white/5 rounded w-full"></div></td>
                      <td className="px-8 py-6"><div className="h-5 bg-white/5 rounded w-40"></div></td>
                      <td className="px-8 py-6"><div className="h-5 bg-white/5 rounded w-16 ml-auto"></div></td>
                    </tr>
                  ))
                ) : filteredStocks.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-8 py-20 text-center text-gray-600 font-medium italic">
                      No matching instruments found in the current session.
                    </td>
                  </tr>
                ) : (
                  filteredStocks.map((stock) => (
                    <tr 
                      key={stock.symbol} 
                      onClick={() => navigate(`/stock/${stock.symbol}`)}
                      className="hover:bg-white/[0.03] transition-all cursor-pointer group"
                    >
                      <td className="px-8 py-6">
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-buy/20 to-buy/5 flex items-center justify-center text-buy font-black text-xs border border-buy/10 group-hover:scale-110 transition-transform">
                            {stock.symbol.substring(0, 2)}
                          </div>
                          <div>
                            <div className="font-black text-white group-hover:text-buy transition-colors">
                              {stock.symbol}
                            </div>
                            <div className="text-[10px] text-gray-600 font-bold uppercase tracking-tighter">Equity • NSE</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-8 py-6">
                        <SignalBadge signal={stock.final_signal} />
                      </td>
                      <td className="px-8 py-6">
                        <div className="flex flex-col gap-2">
                          <div className="flex justify-between items-end">
                            <span className="text-[10px] text-gray-500 font-bold uppercase">Reliability</span>
                            <span className={cn(
                              "text-xs font-black",
                              stock.confidence > 70 ? "text-buy" : stock.confidence > 40 ? "text-yellow-500" : "text-sell"
                            )}>{stock.confidence}%</span>
                          </div>
                          <ConfidenceBar value={stock.confidence} />
                        </div>
                      </td>
                      <td className="px-8 py-6">
                        <span className="text-sm font-bold text-gray-300 group-hover:text-white transition-colors">
                          {stock.dominant_pattern || "Evaluating..."}
                        </span>
                      </td>
                      <td className="px-8 py-6 text-right">
                        <span className="text-xl font-black text-white tabular-nums">
                          {stock.historical_win_rate}%
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </main>
        
        <footer className="mt-12 flex justify-between items-center text-[10px] font-bold text-gray-600 uppercase tracking-[0.2em] border-t border-white/5 pt-8">
          <div>© 2026 PATTERN INTEL SYSTEM • ALL SYSTEMS OPERATIONAL</div>
          <div>REAL-TIME PROCESSING ENABLED • NIFTY BLUE CHIP DATASET</div>
        </footer>
      </div>
    </div>
  );
};

export default Screener;
