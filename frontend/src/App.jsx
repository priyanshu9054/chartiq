import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import Screener from './pages/Screener';
import StockDetail from './pages/StockDetail';
import ChatPanel from './components/ChatPanel';
import { BarChart3, Trophy, LayoutDashboard, Settings, Bell } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

const NavItem = ({ to, icon, label }) => {
  const location = useLocation();
  const isActive = location.pathname === to || (to !== '/' && location.pathname.startsWith(to));
  // Special case for Screener root
  const isReallyActive = (to === '/' && location.pathname === '/') || (to !== '/' && isActive);
  const Icon = icon;

  return (
    <Link 
      to={to}
      className={cn(
        "flex items-center gap-4 px-6 py-4 rounded-2xl transition-all duration-300 group relative overflow-hidden",
        isReallyActive 
          ? "bg-buy text-black font-black shadow-[0_10px_30px_rgba(34,197,94,0.15)] scale-[1.02]" 
          : "text-gray-600 hover:text-white hover:bg-white/[0.03]"
      )}
    >
      <Icon size={20} className={cn(
        "transition-colors",
        isReallyActive ? "text-black" : "group-hover:text-buy"
      )} />
      <span className="text-[11px] uppercase font-black tracking-[0.2em]">{label}</span>
      {isReallyActive && (
        <div className="absolute right-0 top-0 h-full w-1 bg-black/10" />
      )}
    </Link>
  );
};

const Sidebar = () => {
  return (
    <div className="w-[320px] h-screen border-r border-white/5 flex flex-col p-8 sticky top-0 bg-background/50 backdrop-blur-xl z-[100]">
      <div className="flex items-center gap-4 mb-16 px-4 group cursor-pointer">
        <div className="p-3 rounded-2xl bg-gradient-to-br from-buy to-buy/50 text-black shadow-[0_0_30px_rgba(34,197,94,0.2)] group-hover:rotate-12 transition-transform">
          <BarChart3 size={28} />
        </div>
        <div className="font-black text-white text-3xl tracking-tighter leading-[0.8]">
          PATTERN<br/><span className="text-buy">INTEL</span>
        </div>
      </div>

      <nav className="flex-1 space-y-4">
        <div className="px-4 mb-4 text-[9px] font-black text-gray-700 uppercase tracking-[0.4em]">Intelligence Core</div>
        <NavItem to="/" icon={LayoutDashboard} label="Screener" />
        <NavItem to="/leaderboard" icon={Trophy} label="Leaderboard" />
        
        <div className="px-4 mb-4 pt-8 text-[9px] font-black text-gray-700 uppercase tracking-[0.4em]">System Nodes</div>
        <NavItem to="/alerts" icon={Bell} label="Signal Alerts" />
        <NavItem to="/config" icon={Settings} label="Settings" />
      </nav>

      <div className="mt-auto p-6 rounded-[24px] bg-card/[0.5] border border-white/5 relative overflow-hidden group">
        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:scale-125 transition-transform pointer-events-none">
          <BarChart3 size={40} />
        </div>
        <div className="text-[9px] font-black text-gray-600 uppercase tracking-[0.3em] mb-3">Network Layer</div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-2.5 h-2.5 rounded-full bg-buy" />
            <div className="absolute inset-0 w-2.5 h-2.5 rounded-full bg-buy animate-ping opacity-40" />
          </div>
          <span className="text-[10px] font-black text-white uppercase mt-0.5 tracking-widest">Protocol Secured</span>
        </div>
      </div>
    </div>
  );
};

const AppContent = () => {
  const [chatOpen, setChatOpen] = useState(false);
  const location = useLocation();
  
  // Extract symbol from URL for chat context
  const getSymbolContext = () => {
    if (location.pathname.startsWith('/stock/')) {
      return location.pathname.split('/')[2];
    }
    return null;
  };

  return (
    <div className="flex min-h-screen bg-background selection:bg-buy selection:text-black">
      <Sidebar />
      <div className="flex-1 relative">
        <main className="min-h-screen">
          <Routes>
            <Route path="/" element={<Screener />} />
            <Route path="/stock/:symbol" element={<StockDetail />} />
            <Route path="/leaderboard" element={
              <div className="p-20 flex flex-col items-center justify-center text-center mt-32">
                <Trophy size={64} className="text-gray-800 mb-6" />
                <div className="text-gray-700 font-black uppercase tracking-[0.6em] text-xl">Top Patterns Architecture</div>
                <p className="text-gray-800 text-xs font-bold uppercase mt-4 tracking-widest">Integrating Session Weights...</p>
              </div>
            } />
            <Route path="*" element={
              <div className="p-20 flex flex-col items-center justify-center text-center mt-32">
                <div className="text-sell font-black uppercase tracking-[0.6em] text-4xl mb-4">404</div>
                <div className="text-gray-700 font-black uppercase tracking-[0.3em] text-xs">Node Connection Severed</div>
                <Link to="/" className="mt-8 text-buy font-black text-[10px] uppercase tracking-widest underline underline-offset-8">Return to Terminal</Link>
              </div>
            } />
          </Routes>
        </main>
        
        <ChatPanel 
          symbolContext={getSymbolContext()} 
          isOpen={chatOpen} 
          setIsOpen={setChatOpen} 
        />
      </div>
    </div>
  );
};

const App = () => {
  return (
    <Router>
      <AppContent />
    </Router>
  );
};

export default App;
