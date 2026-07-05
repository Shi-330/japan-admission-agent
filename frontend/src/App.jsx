import { useState, useEffect, useRef } from 'react';
import { Send, User, Bot, Loader2, LogOut, Settings } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_KEY;

// ── Auth helpers (Supabase REST API, no SDK needed) ──
async function loginSupabase(email, password) {
  const res = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error_description || err.msg || 'Login failed');
  }
  const data = await res.json();
  return { token: data.access_token, refresh: data.refresh_token, user: data.user };
}

async function registerSupabase(email, password) {
  const res = await fetch(`${SUPABASE_URL}/auth/v1/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.msg || 'Registration failed');
  }
  return res.json();
}

// ── API helpers ──
async function apiCall(path, token, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export default function App() {
  // ── Auth state ──
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState('login'); // login | register
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // ── Chat state ──
  const [messages, setMessages] = useState(() => {
    try { return JSON.parse(localStorage.getItem('chat_v2')) || []; } catch { return []; }
  });
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  // ── Profile state ──
  const [profile, setProfile] = useState(null);
  const [showProfile, setShowProfile] = useState(false);

  // ── Load profile on auth ──
  useEffect(() => {
    if (token) {
      apiCall('/v1/profile', token).then(setProfile).catch(() => {});
    }
  }, [token]);

  // ── Scroll to bottom ──
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    localStorage.setItem('chat_v2', JSON.stringify(messages.slice(-100)));
  }, [messages]);

  // ── Auth handlers ──
  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const r = await loginSupabase(email, password);
      setToken(r.token);
      setUser(r.user || { email });
      setMessages([{ role: 'assistant', content: `欢迎回来, ${email}! 我是你的日本升学顾问，请告诉我你的目标。` }]);
    } catch (err) {
      alert(`登录失败: ${err.message}`);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    try {
      await registerSupabase(email, password);
      alert('注册成功，请查收确认邮件后登录。');
      setAuthMode('login');
    } catch (err) {
      alert(`注册失败: ${err.message}`);
    }
  };

  const handleLogout = () => {
    setToken(null); setUser(null); setProfile(null); setMessages([]);
  };

  // ── Chat ──
  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput(''); setLoading(true);

    try {
      const res = await fetch(`${API}/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ query: input }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const lines = decoder.decode(value, { stream: true }).split('\n');
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const parsed = JSON.parse(line.slice(6));
            if (parsed.done) break;
            if (!parsed.is_status) {
              assistantContent += parsed.content || '';
              setMessages(prev => {
                const last = prev[prev.length - 1];
                if (last?.role === 'assistant') {
                  return [...prev.slice(0, -1), { role: 'assistant', content: assistantContent }];
                }
                return [...prev, { role: 'assistant', content: assistantContent }];
              });
            }
          } catch {}
        }
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: `[错误] 连接失败: ${err.message}` }]);
    } finally {
      setLoading(false);
      apiCall('/v1/profile', token).then(setProfile).catch(() => {});
    }
  };

  // ── Profile form submit ──
  const saveProfile = async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const data = Object.fromEntries(form.entries());
    // Convert numeric fields
    if (data.gpa_score) data.gpa_score = parseFloat(data.gpa_score);
    if (data.gpa_scale) data.gpa_scale = parseFloat(data.gpa_scale);
    if (data.eju_score) data.eju_score = parseInt(data.eju_score);
    try {
      const updated = await apiCall('/v1/profile', token, { method: 'PUT', body: data });
      setProfile(updated);
      setShowProfile(false);
    } catch (err) {
      alert(`保存失败: ${err.message}`);
    }
  };

  // ── Login screen ──
  if (!token) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md">
          <h1 className="text-2xl font-bold text-gray-800 mb-6">日本升学顾问</h1>
          <div className="flex gap-2 mb-6">
            <button
              onClick={() => setAuthMode('login')}
              className={`flex-1 py-2 rounded-lg text-sm font-medium ${authMode === 'login' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600'}`}
            >登录</button>
            <button
              onClick={() => setAuthMode('register')}
              className={`flex-1 py-2 rounded-lg text-sm font-medium ${authMode === 'register' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600'}`}
            >注册</button>
          </div>
          <form onSubmit={authMode === 'login' ? handleLogin : handleRegister}>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="邮箱" required
              className="w-full p-3 border rounded-lg mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <input
              type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="密码" required minLength={6}
              className="w-full p-3 border rounded-lg mb-4 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button type="submit" className="w-full py-3 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition">
              {authMode === 'login' ? '登录' : '注册'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // ── Main app ──
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-80 bg-white border-r flex flex-col shrink-0">
        <div className="p-6 border-b">
          <h1 className="text-lg font-bold text-gray-800">升学顾问</h1>
          <p className="text-xs text-gray-400 mt-1">{user?.email}</p>
        </div>

        <div className="p-4 border-b">
          <button onClick={() => setShowProfile(!showProfile)}
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-indigo-600 w-full p-2 rounded-lg hover:bg-gray-50">
            <Settings size={16} /> 学生背景
          </button>
          {profile && (
            <div className="mt-2 text-xs text-gray-500 space-y-1">
              <div>JLPT: {profile.jlpt_level} | 英语: {profile.english_score || '-'}</div>
              {profile.gpa_score > 0 && <div>GPA: {profile.gpa_score}/{profile.gpa_scale}</div>}
              <div>专业: {profile.target_major || '未设定'}</div>
              {profile.research_area && <div>方向: {profile.research_area}</div>}
              {profile.facts && Object.keys(profile.facts).length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-indigo-600">AI 已记录 ({Object.keys(profile.facts).length}条)</summary>
                  {Object.entries(profile.facts).map(([k, v]) => (
                    <div key={k} className="ml-2">{k}: {v}</div>
                  ))}
                </details>
              )}
            </div>
          )}
        </div>

        {/* Profile edit form */}
        {showProfile && (
          <div className="p-4 border-b bg-gray-50">
            <form onSubmit={saveProfile} className="space-y-2 text-sm">
              <select name="jlpt_level" defaultValue={profile?.jlpt_level || '无'}
                className="w-full p-2 border rounded">
                {['无','N5','N4','N3','N2','N1'].map(l => <option key={l}>{l}</option>)}
              </select>
              <input name="english_score" defaultValue={profile?.english_score || ''}
                placeholder="英语: TOEFL 95" className="w-full p-2 border rounded" />
              <div className="flex gap-2">
                <input name="gpa_score" type="number" step="0.1" defaultValue={profile?.gpa_score || ''}
                  placeholder="GPA" className="w-1/2 p-2 border rounded" />
                <select name="gpa_scale" defaultValue={profile?.gpa_scale || 4.0}
                  className="w-1/2 p-2 border rounded">
                  {[4.0, 4.3, 5.0, 100].map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <input name="target_major" defaultValue={profile?.target_major || ''}
                placeholder="目标专业" className="w-full p-2 border rounded" />
              <input name="research_area" defaultValue={profile?.research_area || ''}
                placeholder="研究方向" className="w-full p-2 border rounded" />
              <input name="undergraduate_school" defaultValue={profile?.undergraduate_school || ''}
                placeholder="本科院校" className="w-full p-2 border rounded" />
              <button type="submit" className="w-full py-2 bg-indigo-600 text-white rounded text-sm">
                保存
              </button>
            </form>
          </div>
        )}

        <div className="mt-auto p-4 border-t">
          <button onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-red-500 w-full p-2">
            <LogOut size={16} /> 退出
          </button>
        </div>
      </aside>

      {/* Chat area */}
      <main className="flex-1 flex flex-col">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-gray-700' : 'bg-indigo-600'}`}>
                {msg.role === 'user' ? <User size={14} className="text-white" /> : <Bot size={14} className="text-white" />}
              </div>
              <div className={`max-w-[75%] p-4 rounded-2xl text-sm leading-relaxed ${msg.role === 'user' ? 'bg-gray-800 text-white' : 'bg-white border shadow-sm'}`}>
                <div className="whitespace-pre-wrap">{msg.content}</div>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex items-center gap-2 text-gray-400 text-sm ml-11">
              <Loader2 size={14} className="animate-spin" /> 思考中...
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 border-t bg-white">
          <div className="max-w-3xl mx-auto flex gap-3">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendMessage()}
              disabled={loading}
              placeholder="输入你的留学疑问..."
              className="flex-1 p-3 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="w-12 h-12 flex items-center justify-center bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition shrink-0"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
