import React, { useState, useEffect, useRef } from 'react';
import { Send, X, Bot, User, ChevronLeft, ChevronRight, Hash, Sparkles, ChevronDown, ChevronUp, Database } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { sendChatMessage } from '../lib/api';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

const ChatMessageItem = ({ msg }) => {
  const [showSource, setShowSource] = useState(false);
  
  return (
    <div className={cn(
      "flex flex-col gap-3 group animate-slide-in",
      msg.role === 'user' ? "items-end" : "items-start"
    )}>
      <div className="flex items-center gap-2 text-[10px] font-black text-gray-600 uppercase tracking-widest">
        {msg.role === 'user' ? (
          <><span className="text-gray-400">{msg.timestamp}</span> • <span className="text-white">Operator</span></>
        ) : (
          <><span className="text-buy">Quant Engine</span> • <span className="text-gray-400">{msg.timestamp}</span></>
        )}
      </div>
      <div className={cn(
        "p-5 rounded-2xl text-sm leading-relaxed shadow-lg flex flex-col gap-3",
        msg.role === 'user' 
          ? "bg-buy text-black font-bold rounded-tr-none max-w-[90%]" 
          : "bg-card text-gray-300 border border-white/10 rounded-tl-none max-w-[95%] font-medium"
      )}>
        {msg.role === 'user' ? (
          <div>{msg.content}</div>
        ) : (
          <div className="markdown-body text-sm font-medium leading-relaxed overflow-hidden">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                p: (props) => { const { node: _node, ...rest } = props; return <p className="mb-2 last:mb-0" {...rest} />; },
                ul: (props) => { const { node: _node, ...rest } = props; return <ul className="list-disc ml-4 mb-2" {...rest} />; },
                ol: (props) => { const { node: _node, ...rest } = props; return <ol className="list-decimal ml-4 mb-2" {...rest} />; },
                li: (props) => { const { node: _node, ...rest } = props; return <li className="mb-1" {...rest} />; },
                strong: (props) => { const { node: _node, ...rest } = props; return <strong className="font-bold text-white" {...rest} />; },
                h1: (props) => { const { node: _node, ...rest } = props; return <h1 className="text-lg font-bold text-white mb-2" {...rest} />; },
                h2: (props) => { const { node: _node, ...rest } = props; return <h2 className="text-md font-bold text-white mb-2" {...rest} />; },
                h3: (props) => { const { node: _node, ...rest } = props; return <h3 className="text-sm font-bold text-white mb-2" {...rest} />; },
                a: (props) => { const { node: _node, ...rest } = props; return <a className="text-buy hover:underline" {...rest} />; }
              }}
            >
               {msg.content}
            </ReactMarkdown>
          </div>
        )}
        
        {msg.raw_data && (
          <div className="mt-2 border-t border-white/10 pt-3">
            <button 
              onClick={() => setShowSource(!showSource)}
              className="flex items-center gap-2 text-xs font-bold text-buy hover:text-buy/80 transition-colors uppercase tracking-wider"
            >
              <Database size={12} />
              {showSource ? 'Hide Source Data' : 'View Source Data'}
              {showSource ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            
            {showSource && (
              <div className="mt-3 bg-black/50 p-3 rounded-lg border border-white/5 overflow-x-auto">
                <pre className="text-[10px] text-gray-400 font-mono">
                  {JSON.stringify(msg.raw_data, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const ChatPanel = ({ symbolContext, isOpen, setIsOpen }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMsg = { role: 'user', content: input, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await sendChatMessage(input, "session-v1", symbolContext);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: response?.response || "No analysis available for this query.",
        raw_data: response?.raw_data,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
    } catch {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: "Operational error: Failed to connect to the intelligence server. Verify backend status.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "fixed top-1/2 -translate-y-1/2 glass p-1.5 rounded-l-xl border-y border-l border-white/10 z-[60] transition-all duration-300 group",
          isOpen ? "right-[450px]" : "right-0 shadow-[0_0_20px_rgba(34,197,94,0.1)]"
        )}
      >
        <div className={cn(
          "bg-white/5 p-2 rounded-lg transition-colors group-hover:bg-buy/10 group-hover:text-buy",
          !isOpen && "animate-pulse border border-buy/20"
        )}>
          {isOpen ? <ChevronRight size={24} /> : <ChevronLeft size={24} />}
        </div>
      </button>

      <div className={cn(
        "fixed right-0 top-0 h-screen w-[450px] bg-background border-l border-white/10 z-50 transition-transform duration-500 cubic-bezier(0.4, 0, 0.2, 1) flex flex-col shadow-[0_0_50px_rgba(0,0,0,0.5)]",
        isOpen ? "translate-x-0" : "translate-x-full"
      )}>
        {/* Header */}
        <div className="p-8 border-b border-white/5 flex justify-between items-center bg-white/[0.02] relative overflow-hidden">
          <div className="absolute top-0 right-0 p-12 opacity-5 pointer-events-none">
            <Sparkles size={120} className="text-buy" />
          </div>
          <div className="relative z-10">
            <h2 className="text-2xl font-black text-white flex items-center gap-3 tracking-tighter">
              <div className="p-2 rounded-lg bg-buy/10 text-buy">
                <Bot size={24} />
              </div>
              Quant Analyst
            </h2>
            <div className="flex items-center gap-2 mt-2">
              <span className="w-1.5 h-1.5 rounded-full bg-buy animate-pulse" />
              <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">
                Active Node: <span className="text-white">{symbolContext || 'Global'}</span>
              </span>
            </div>
          </div>
          <button 
            onClick={() => setIsOpen(false)} 
            className="p-2 text-gray-600 hover:text-white hover:bg-white/5 rounded-lg transition-all relative z-10"
          >
            <X size={20} />
          </button>
        </div>

        {/* Messages */}
        <div 
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-8 space-y-8 no-scrollbar scroll-smooth"
        >
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center space-y-6 opacity-30">
              <div className="p-6 rounded-full bg-white/5 border border-white/5">
                <Bot size={48} className="text-buy" />
              </div>
              <div className="max-w-xs space-y-2">
                <p className="font-black text-white italic">"Alpha at your fingertips"</p>
                <p className="text-xs uppercase tracking-widest">Ask for pattern breakdowns, risk assessments, or target levels for {symbolContext || 'any stock'}.</p>
              </div>
            </div>
          )}
          
          {messages.map((msg, i) => (
            <ChatMessageItem key={i} msg={msg} />
          ))}
          
          {isLoading && (
            <div className="flex flex-col gap-2 items-start animate-pulse">
              <div className="flex items-center gap-2 text-[10px] font-black text-buy uppercase tracking-widest">
                Refining Signal...
              </div>
              <div className="bg-card/50 border border-white/5 p-4 rounded-2xl rounded-tl-none w-32 h-12 flex items-center justify-center gap-1">
                <div className="w-1.5 h-1.5 bg-buy rounded-full animate-bounce [animation-delay:-0.3s]" />
                <div className="w-1.5 h-1.5 bg-buy rounded-full animate-bounce [animation-delay:-0.15s]" />
                <div className="w-1.5 h-1.5 bg-buy rounded-full animate-bounce" />
              </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-8 bg-card/30 border-t border-white/5 flex flex-col gap-4">
          <div className="flex flex-wrap gap-2 mb-2">
            {["What is the RSI?", "Should I hold for 30 days?", "What is the dominant pattern?"].map((q, idx) => (
              <button
                key={idx}
                onClick={() => setInput(q)}
                className="text-[10px] md:text-xs px-3 py-1.5 rounded-full border border-white/10 bg-white/5 text-gray-300 hover:bg-buy/20 hover:text-buy hover:border-buy/30 transition-all font-medium text-left"
              >
                {q}
              </button>
            ))}
          </div>
          <div className="relative group">
            <div className="absolute inset-0 bg-buy/5 rounded-2xl blur-xl opacity-0 group-focus-within:opacity-100 transition-opacity pointer-events-none" />
            <div className="relative flex items-center gap-3 bg-background border border-white/10 rounded-2xl p-2 pl-4 focus-within:border-buy/40 transition-all">
              <Hash size={18} className="text-gray-700" />
              <input 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                placeholder={symbolContext ? `Query ${symbolContext}...` : "Type a market query..."}
                className="flex-1 bg-transparent border-none py-3 focus:outline-none font-sans text-sm text-white placeholder:text-gray-700"
              />
              <button 
                onClick={handleSend}
                disabled={isLoading}
                className="bg-buy hover:bg-buy/90 active:scale-95 text-black p-3 rounded-xl transition-all shadow-[0_0_15px_rgba(34,197,94,0.2)] disabled:opacity-50"
              >
                <Send size={18} />
              </button>
            </div>
          </div>
          <div className="mt-4 text-[9px] text-gray-700 font-bold text-center uppercase tracking-[0.3em]">
            SYSTEM_PROTOCOL: SECURE • AI_LATENCY: OPTIMIZED
          </div>
        </div>
      </div>
    </>
  );
};

export default ChatPanel;
