import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Send, User, Bot, Loader2, ClipboardCheck, LayoutDashboard, Database } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: '🌸 欢迎回来！我已经准备好为你进行留学规划了。请补充你的背景信息以便我给出更精准的建议。' }
  ]);
  const [input, setInput] = useState('');
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, status]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      // 默认空画像，实际应从 State/Supabase 获取
      const mockProfile = {
        jlpt_level: "无",
        eju_score: 0,
        gpa: 0.0,
        target_major: "未设定",
        undergraduate_school: "未设定",
        english_score: "未参加"
      };

      const response = await fetch(`${API_BASE_URL}/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input, user_profile: mockProfile })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });

        // 捕捉状态标记
        // 捕捉状态标记并过滤掉它们
        const statusMatches = chunk.match(/\[STATUS:(.*?)\]/g);
        if (statusMatches) {
          statusMatches.forEach(match => {
            const s = match.match(/\[STATUS:(.*?)\]/)[1];
            setStatus(s);
          });
        }

        // 移除状态标记后的纯内容
        const cleanChunk = chunk.replace(/\[STATUS:.*?\]/g, '');
        if (cleanChunk) {
          assistantContent += cleanChunk;
          setMessages(prev => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg.role === 'assistant') {
              return [...prev.slice(0, -1), { role: 'assistant', content: assistantContent }];
            } else {
              return [...prev, { role: 'assistant', content: assistantContent }];
            }
          });
        }
      }
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ 抱歉，连接服务器失败。请检查后端是否正常启动。' }]);
    } finally {
      setLoading(false);
      setStatus(null);
    }
  };

  return (
    <div className="flex h-screen w-screen max-w-none bg-transparent overflow-hidden">
      {/* 侧边栏 */}
      <aside className="w-80 bg-white/40 backdrop-blur-xl border-r border-white/20 p-6 flex flex-col gap-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="bg-primary p-2 rounded-lg">
            <ClipboardCheck className="text-white w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent italic">
            Japan Admission
          </h1>
        </div>

        <div className="premium-card bg-primary-light/50 border-primary/20">
          <h2 className="flex items-center gap-2 text-primary-dark font-bold mb-2">
            <LayoutDashboard size={18} /> 申请准备度
          </h2>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: '45%' }}
              className="h-full bg-primary"
            />
          </div>
          <p className="text-xs text-primary-dark mt-2">当前处于：早期调研阶段 (45%)</p>
        </div>

        <nav className="flex flex-col gap-2 mt-auto">
          <button className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/50 transition-all text-gray-700">
            <User size={20} /> 背景画像管理
          </button>
          <button className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/50 transition-all text-gray-700">
            <Database size={20} /> 院校数据库
          </button>
        </nav>
      </aside>

      {/* 主聊天区 */}
      <main className="flex-1 flex flex-col items-center justify-center p-8 bg-transparent">
        <div className="w-full max-w-4xl h-full flex flex-col gap-6 relative">

          {/* 消息历史 */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto pr-4 flex flex-col gap-6 scroll-smooth"
          >
            <AnimatePresence>
              {messages.map((msg, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                >
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center shadow-md shrink-0 ${msg.role === 'user' ? 'bg-secondary' : 'bg-primary'
                    }`}>
                    {msg.role === 'user' ? <User className="text-white" size={20} /> : <Bot className="text-white" size={20} />}
                  </div>
                  <div className={`premium-card !p-4 max-w-[80%] ${msg.role === 'user' ? '!bg-secondary-light !border-secondary/10' : ''
                    }`}>
                    <p className="text-gray-800 leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {/* 状态反馈 */}
            {status && (
              <div className="flex items-center gap-2 text-primary text-sm font-medium animate-pulse ml-14">
                <Loader2 size={16} className="animate-spin" />
                正在 {status === 'UNDERSTANDING' ? '理解问题' :
                  status === 'RETRIEVING' ? '检索院校库' :
                    status === 'THINKING' ? '深度思考' : '组织语言'}...
              </div>
            )}
          </div>

          {/* 输入框 */}
          <div className="relative">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
              disabled={loading}
              placeholder="输入你的留学疑问..."
              className="premium-input !pr-16 !py-4 text-lg"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 w-12 h-12 flex items-center justify-center bg-primary rounded-xl text-white hover:scale-105 active:scale-95 transition-all disabled:opacity-50"
            >
              <Send size={20} />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
