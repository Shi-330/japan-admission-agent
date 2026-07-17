import { useState, useEffect, useRef, useCallback } from 'react';
import { Send, User, Bot, Loader2, LogOut, Settings, LayoutGrid, MessageCircle, Calendar, Search, FileText } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Toaster, toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import CalendarView from '@/components/CalendarView';
import DashboardView from '@/components/DashboardView';
import OutreachDraft from '@/components/OutreachDraft';
import ReminderBell from '@/components/ReminderBell';
import ReminderDrawer from '@/components/ReminderDrawer';

// Same-origin by default: FastAPI (local) and nginx (prod) both serve the SPA and /v1 API
// on one domain. VITE_API_URL is only for running the SPA on a different host (e.g. vite dev :5173).
const API = import.meta.env.VITE_API_URL || '';
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_KEY;

// ── Plaza CN→JP school matching (shared by count badge + grid so they never disagree) ──
const CN2JP = { '计算机':['情報工学','コンピュータ科学','情報理工'], '人工智能':['知能情報学','人工知能','AI'], '电子':['電気電子','電子情報学'], '机械':['機械工学','機械創造工学'], '数学':['数理工学','数理情報学'], '通信':['情報通信','通信情報システム'], '网络':['情報ネットワーク','メディアネットワーク'], '生命':['生命人間情報科学','バイオ情報工学'], '数据':['データ科学','データサイエンス'], '金融':['社会情報学','システム情報学'], '信息':['情報理工','情報工学','情報科学'], '情报':['情報理工','情報工学','情報科学'] };
function schoolMatches(s, filter) {
  if (!filter) return true;
  const text = [s.name, ...(s.majors || []), ...(s.tags || [])].join(' ').toLowerCase();
  return filter.toLowerCase().split(/\s+/).filter(Boolean).some(w => {
    if (text.includes(w)) return true;
    const aliases = CN2JP[w];
    return aliases ? aliases.some(a => text.includes(a)) : false;
  });
}

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
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // Supabase returns 200 with identities:[] when email confirmation is required — that's success
    if (data.identities && data.identities.length === 0 && !data.msg) {
      return data; // silently success, user needs to confirm email
    }
    const msg = data.msg || data.error_description || 'Registration failed';
    throw new Error(msg);
  }
  return data;
}

async function resetPasswordSupabase(email) {
  const res = await fetch(`${SUPABASE_URL}/auth/v1/recover`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.msg || 'Password reset failed');
  }
}

// ── Token refresh (Supabase access tokens expire after ~1h; without this every expiry forces a re-login) ──
let refreshPromise = null;
async function refreshSupabaseToken() {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const rt = localStorage.getItem('refresh_token');
      if (!rt) throw new Error('no refresh token');
      const res = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY },
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (!res.ok) {
        localStorage.removeItem('refresh_token');
        throw new Error('refresh failed');
      }
      const data = await res.json();
      localStorage.setItem('jwt', data.access_token);
      if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
      // Sync React token state (apiCall lives outside the component tree)
      window.dispatchEvent(new CustomEvent('jwt-refreshed', { detail: data.access_token }));
      return data.access_token;
    })().finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

// ── API helpers ──
async function apiCall(path, token, { method = 'GET', body } = {}, _retried = false) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (res.status === 401 && !_retried && localStorage.getItem('refresh_token')) {
    const newToken = await refreshSupabaseToken().catch(() => null);
    if (newToken) return apiCall(path, newToken, { method, body }, true);
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export default function App() {
  // ── Auth state ──
  const [token, setToken] = useState(() => localStorage.getItem('jwt'));
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState('login'); // login | register
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [forgotPwd, setForgotPwd] = useState(false);
  // ── Toast uses Sonner (below) ──
  const showToast = (text, type = 'error') => {
    type === 'success' ? toast.success(text) : toast.error(text);
  };

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

  // ── Load profile + catalog on auth ──
  useEffect(() => {
    if (token) {
      apiCall('/v1/profile', token).then(setProfile).catch(() => {});
      apiCall('/v1/schools', token).then(r => setCatalog(r.schools)).catch(e => console.error('school catalog load failed:', e.message));
    }
  }, [token]);

  // ── Persist session token across refreshes ──
  useEffect(() => {
    if (token) localStorage.setItem('jwt', token);
    else localStorage.removeItem('jwt');
  }, [token]);

  // ── Scroll to bottom ──
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    localStorage.setItem('chat_v2', JSON.stringify(messages.slice(-100)));
  }, [messages]);

  // ── Greeting helper ──
  const loadGreeting = async (t, { resetMessages = true } = {}) => {
    setGreetingLoading(true);
    try {
      const g = await apiCall('/v1/greeting', t);
      setGreeting(g);
      if (resetMessages) setMessages([{ role: 'assistant', content: g.message }]);
    } catch {
      const fallback = { message: '欢迎回来！我是你的日本升学顾问，请告诉我你的目标。', profile_completeness: { filled: 0, total: 6, percentage: 0 }, next_actions: [], counts: { total_apps: 0, overdue_profs: 0, upcoming_deadlines: 0 } };
      setGreeting(fallback);
      if (resetMessages) setMessages([{ role: 'assistant', content: fallback.message }]);
    } finally {
      setGreetingLoading(false);
    }
  };

  // ── Restore session on refresh: hydrate dashboard greeting, keep persisted chat ──
  useEffect(() => { if (token) loadGreeting(token, { resetMessages: false }); }, []);

  // ── Keep React token in sync when apiCall transparently refreshes an expired JWT ──
  useEffect(() => {
    const sync = (e) => setToken(e.detail);
    window.addEventListener('jwt-refreshed', sync);
    return () => window.removeEventListener('jwt-refreshed', sync);
  }, []);

  // ── Auth handlers ──
  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    try {
      const r = await loginSupabase(email, password);
      setToken(r.token);
      if (r.refresh) localStorage.setItem('refresh_token', r.refresh);
      setUser(r.user || { email });
      await loadGreeting(r.token);
    } catch (err) {
      const raw = err.message;
      const msg = raw === 'Failed to fetch'
        ? '无法连接服务器，请检查网络'
        : raw.includes('Invalid login')
        ? '邮箱或密码错误'
        : raw.includes('Email not confirmed')
        ? '邮箱未验证，请先点击确认邮件中的链接'
        : raw.includes('security purposes')
        ? '操作太频繁，稍等片刻再试'
        : `登录失败: ${raw}`;
      toast.error(msg);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    try {
      await registerSupabase(email, password);
      toast.success('注册成功，请查收确认邮件后登录。');
      setAuthMode('login');
    } catch (err) {
      const raw = err.message;
      const msg = raw === 'Failed to fetch'
        ? '无法连接服务器，请检查网络'
        : raw.includes('already registered') || raw.includes('already exists')
        ? '该邮箱已注册，请直接登录'
        : raw.includes('security purposes')
        ? '操作太频繁，稍等片刻再试'
        : raw.includes('password')
        ? '密码长度至少 6 位'
        : `注册失败: ${raw}`;
      toast.error(msg);
    } finally {
      setAuthLoading(false);
    }
  };

  // 跟踪密码重置尝试，5 分钟内多次触发提醒检查邮箱
  const resetAttempts = useRef([]);

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    if (!email) { toast.error('请输入邮箱地址'); return; }

    const now = Date.now();
    resetAttempts.current = resetAttempts.current.filter(t => now - t < 300000);
    resetAttempts.current.push(now);

    setAuthLoading(true);
    try {
      await resetPasswordSupabase(email);
      toast.success('重置邮件已发送，请查收邮箱');
      if (resetAttempts.current.length >= 2) {
        setTimeout(() => {
          toast('多次未收到邮件？请检查邮箱地址是否输入正确', { duration: 6000 });
        }, 2000);
      }
      setForgotPwd(false);
    } catch (err) {
      const raw = err.message;
      const msg = raw === 'Failed to fetch'
        ? '无法连接服务器，请检查网络'
        : raw.includes('security purposes')
        ? '操作太频繁，请 60 秒后再试'
        : raw.includes('User not found') || raw.includes('user not found')
        ? '该邮箱未注册'
        : raw.includes('rate limit') || raw.includes('too many')
        ? '请求太频繁，请稍后再试'
        : `发送失败: ${raw}`;
      toast.error(msg);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('refresh_token');
    setToken(null); setUser(null); setProfile(null); setStage(null); setMessages([]);
  };

  // ── Stage state ──
  const [stage, setStage] = useState(null);
  const [advancing, setAdvancing] = useState(null);
  const [showAddSchool, setShowAddSchool] = useState(false);
  const [newSchool, setNewSchool] = useState('');
  const [newSchoolStage, setNewSchoolStage] = useState('preparing');
  // ── Card edit state ──
  const [editCard, setEditCard] = useState(null); // school name being edited
  const [editProfName, setEditProfName] = useState('');
  const [editProfStatus, setEditProfStatus] = useState('sent');
  const [editDeadlineKey, setEditDeadlineKey] = useState('');
  const [editDeadlineVal, setEditDeadlineVal] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null); // school name to delete
  // ── Plaza state ──
  const [greeting, setGreeting] = useState(null);
  const [greetingLoading, setGreetingLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('home'); // home | chat | plaza | calendar
  const [catalog, setCatalog] = useState([]);
  const [plazaFilter, setPlazaFilter] = useState('');
  const [selectedProf, setSelectedProf] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [inputOpen, setInputOpen] = useState(true);
  // ── Reminder drawer state ──
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerData, setDrawerData] = useState({ reminders: [], loading: false, error: false, onRefresh: () => {} });
  const reminderToastIds = useRef(new Set());

  const handleNewReminders = useCallback((newItems) => {
    for (const item of newItems) {
      if (!reminderToastIds.current.has(item.id)) {
        reminderToastIds.current.add(item.id);
        toast(item.message, { duration: 5000 });
      }
    }
  }, []);

  const handleOpenDrawer = useCallback((data) => {
    setDrawerData(data);
    setDrawerOpen(true);
  }, []);

  const handleDrawerClose = useCallback(() => {
    setDrawerOpen(false);
  }, []);

  const handleReminderAction = useCallback((reminder) => {
    setDrawerOpen(false);
    const action = reminder.action;
    if (!action) return;
    if (action.type === 'draft_outreach') {
      // Open OutreachDraft dialog with pre-filled school/professor
      setSelectedProf({ school: action.school, professorName: action.professor });
    } else if (action.type === 'goto_calendar') {
      setActiveTab('calendar');
    } else if (action.type === 'open_profile') {
      setShowProfile(true);
    }
  }, []);
  useEffect(() => {
    if (token) {
      apiCall('/v1/stage', token).then(setStage).catch(() => {});
    }
  }, [token, profile]); // refresh stage whenever profile changes (incl. applications)

  const advanceStage = async (target, school) => {
    const key = school || target;
    setAdvancing(key);
    try {
      const body = { target_stage: target };
      if (school) body.school = school;
      const r = await apiCall('/v1/stage/advance', token, { method: 'POST', body });
      if (!r.unchanged) {
        // Refresh full stage data
        const updated = await apiCall('/v1/stage', token);
        setStage(updated);
      }
    } catch (err) {
      showToast(`阶段切换失败: ${err.message}`);
    } finally {
      setAdvancing(null);
    }
  };

  const addSchool = async (e) => {
    e.preventDefault();
    if (!newSchool.trim()) return;
    try {
      const r = await apiCall('/v1/applications', token, {
        method: 'POST',
        body: { school: newSchool.trim(), stage: newSchoolStage }
      });
      // Refresh stage data
      const updated = await apiCall('/v1/stage', token);
      setStage(updated);
      setNewSchool('');
      setNewSchoolStage('preparing');
      setShowAddSchool(false);
    } catch (err) {
      showToast(`添加失败: ${err.message}`);
    }
  };

  const removeSchool = async () => {
    const school = deleteTarget;
    if (!school) return;
    try {
      await apiCall(`/v1/applications?school=${encodeURIComponent(school)}`, token, { method: 'DELETE' });
      const updated = await apiCall('/v1/stage', token);
      setStage(updated);
      showToast(`已删除「${school}」`, 'success');
    } catch (err) {
      showToast(`删除失败: ${err.message}`);
    } finally {
      setDeleteTarget(null);
    }
  };

  const updateApplication = async (school, updates) => {
    try {
      await apiCall('/v1/applications', token, { method: 'POST', body: { school, ...updates } });
      const [updated] = await Promise.all([apiCall('/v1/stage', token), loadGreeting(token, { resetMessages: false })]);
      setStage(updated);
      showToast('已更新', 'success');
    } catch (err) {
      showToast(`更新失败: ${err.message}`);
    }
  };

  // ── Chat ──
  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput(''); setLoading(true);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 45000);
    try {
      const chatBody = JSON.stringify({ query: input, history: messages.slice(-6) });
      const doFetch = (t) => fetch(`${API}/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${t}` },
        body: chatBody,
        signal: controller.signal,
      });
      let res = await doFetch(token);
      if (res.status === 401 && localStorage.getItem('refresh_token')) {
        const newToken = await refreshSupabaseToken().catch(() => null);
        if (newToken) res = await doFetch(newToken);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';
      let suggested = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const lines = decoder.decode(value, { stream: true }).split('\n');
        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          try {
            const parsed = JSON.parse(line.startsWith('data: ') ? line.slice(6) : line.slice(5));
            if (parsed.nav_suggestion) {
              suggested = [{ type: 'nav', ...parsed.nav_suggestion }];
              break;
            }
            if (parsed.suggested_schools) {
              suggested = parsed.suggested_schools;
              break;
            }
            if (parsed.done) {
              break;
            }
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
          } catch (e) { console.warn('SSE parse:', e, line.slice(0, 80)); }
        }
      }

      // After streaming done, show suggestions
      if (suggested.length > 0) {
        if (suggested[0].type === 'nav') {
          // Navigation suggestion
          const nav = suggested[0];
          setMessages(prev => [...prev, {
            role: 'assistant', content: '',
            navSuggestion: { prompt: nav.prompt, filter: nav.filter, action: nav.action }
          }]);
        } else {
          // School suggestions
          setMessages(prev => [...prev, {
            role: 'assistant', content: '',
            suggestedSchools: suggested
          }]);
        }
      }
    } catch (err) {
      const msg = err.name === 'AbortError' ? '回复超时，请重试' : `连接失败: ${err.message}`;
      setMessages(prev => [...prev, { role: 'assistant', content: `[错误] ${msg}` }]);
    } finally {
      clearTimeout(timeout);
      setLoading(false);
      // Ensure last assistant message is visible even if stream was empty
      if (!assistantContent && suggested.length === 0) {
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant' && !last.content) {
            return [...prev.slice(0, -1), { role: 'assistant', content: '抱歉，没有收到回复，请重试。' }];
          }
          if (last?.role !== 'assistant') {
            return [...prev, { role: 'assistant', content: '抱歉，没有收到回复，请重试。' }];
          }
          return prev;
        });
      }
      apiCall('/v1/profile', token).then(setProfile).catch(() => {});
    }
  };

  // ── Profile form submit ──
  const saveProfile = async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const raw = Object.fromEntries(form.entries());
    // Clean: drop empty strings, convert numerics
    const data = {};
    for (const [k, v] of Object.entries(raw)) {
      if (v === '' || v === null || v === undefined) continue;
      if (k === 'gpa_score' || k === 'gpa_scale') data[k] = parseFloat(v);
      else if (k === 'eju_score') data[k] = parseInt(v);
      else data[k] = v;
    }
    try {
      const updated = await apiCall('/v1/profile', token, { method: 'PUT', body: data });
      setProfile(updated);
      setShowProfile(false);
    } catch (err) {
      showToast(`保存失败: ${err.message}`);
    }
  };

  // ── Login screen ──
  if (!token) {
    return (
      <>
        <Toaster position="top-center" richColors closeButton />
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md">
          <h1 className="text-2xl font-bold text-gray-800 mb-6">日本升学顾问</h1>
          <div className="flex gap-2 mb-6">
            <Button
              onClick={() => { setAuthMode('login'); setForgotPwd(false); }}
              variant={authMode === 'login' && !forgotPwd ? 'default' : 'secondary'}
              className="flex-1"
            >登录</Button>
            <Button
              onClick={() => { setAuthMode('register'); setForgotPwd(false); }}
              variant={authMode === 'register' ? 'default' : 'secondary'}
              className="flex-1"
            >注册</Button>
          </div>
          <form onSubmit={
            forgotPwd ? handleForgotPassword :
            authMode === 'login' ? handleLogin : handleRegister
          } className="space-y-3">
            <Input type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="邮箱" required />
            {!forgotPwd && (
              <Input type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="密码" required minLength={6} />
            )}
            <Button type="submit" className="w-full" disabled={authLoading}>
              {authLoading ? '处理中...' : forgotPwd ? '发送重置邮件' : (authMode === 'login' ? '登录' : '注册')}
            </Button>
            {authMode === 'login' && (
              <button type="button" onClick={() => setForgotPwd(!forgotPwd)}
                className="w-full text-xs text-gray-400 hover:text-indigo-500 mt-1">
                {forgotPwd ? '返回登录' : '忘记密码？'}
              </button>
            )}
          </form>
        </div>
      </div>
      </>
    );
  }

  // ── Main app ──
  return (
    <div className="flex h-screen bg-background">
      <Toaster position="top-center" richColors closeButton />
      {/* Sidebar */}
      <aside className={`bg-card border-r border-border flex flex-col shrink-0 overflow-hidden transition-all duration-200 ${sidebarOpen ? 'w-80' : 'w-12'}`}>
        <div className="p-3 border-b border-border flex justify-center">
          <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(!sidebarOpen)} title={sidebarOpen ? '收起' : '展开'}>
            <LayoutGrid size={14} />
          </Button>
        </div>
        <div className={`flex-1 overflow-hidden flex flex-col ${sidebarOpen ? '' : 'hidden'}`}>

        <div className="flex-1 overflow-y-auto">
        {/* Stage + Applications */}
        {stage && (
          <div className="p-4 border-b border-border">
            {/* Single progress bar — only show when no per-school cards */}
            {(!stage.applications || stage.applications.length === 0) && (
              <>
                <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">申请进度</h3>
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div className="h-full bg-primary/100 rounded-full transition-all"
                      style={{ width: `${(stage.progress || 0) * 100}%` }}></div>
                  </div>
                  <span className="text-xs text-gray-400">{Math.round((stage.progress || 0) * 100)}%</span>
                </div>
                <p className="text-sm font-medium text-indigo-700">{stage.label}</p>
                <p className="text-xs text-gray-500 mt-1">{stage.description}</p>
                {stage.actions?.length > 0 && (
                  <details className="mt-2">
                    <summary className="text-xs text-indigo-500 cursor-pointer">建议行动 ({stage.actions.length})</summary>
                    <ul className="mt-1 text-xs text-gray-500 space-y-0.5 ml-3">
                      {stage.actions.map((a, i) => <li key={i} className="list-disc">{a}</li>)}
                    </ul>
                  </details>
                )}
              </>
            )}

            {/* Per-school cards */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-gray-400 uppercase">
                  {stage.applications?.length > 0 ? `志愿校 (${stage.applications.length})` : '各校追踪'}
                </h4>
                <Button onClick={() => setShowAddSchool(!showAddSchool)}
                  className="text-xs px-2 py-0.5 rounded bg-primary/10 hover:bg-indigo-100 text-primary transition font-medium"
                  title="添加学校">+ 添加</Button>
              </div>

              {showAddSchool && (
                <form onSubmit={addSchool} className="border rounded-lg p-2.5 bg-primary/10 space-y-1.5">
                  <Input value={newSchool} onChange={e => setNewSchool(e.target.value)}
                    placeholder="学校名称，如：京都大学 情报理工"
                    className="w-full text-xs p-2 border rounded focus:outline-none focus:ring-1 focus:ring-indigo-400" autoFocus />
                  <Select value={newSchoolStage} onChange={e => setNewSchoolStage(e.target.value)}
                    className="w-full text-xs p-2 border rounded focus:outline-none focus:ring-1 focus:ring-indigo-400">
                    <option value="browsing">关注中</option>
                    <option value="preparing">准备阶段</option>
                    <option value="contacting">套磁阶段</option>
                    <option value="applying">出愿阶段</option>
                    <option value="exam">考试阶段</option>
                    <option value="waiting">等待结果</option>
                    <option value="decided">确定去向</option>
                  </Select>
                  <div className="flex gap-2">
                    <Button type="submit" disabled={!newSchool.trim()}
                      className="text-xs px-3 py-1.5 rounded bg-primary text-primary-foreground hover:bg-indigo-700 disabled:opacity-30 transition flex-1">添加</Button>
                    <Button type="button" onClick={() => setShowAddSchool(false)}
                      className="text-xs px-3 py-1.5 rounded bg-white text-gray-500 hover:bg-gray-100 transition border">取消</Button>
                  </div>
                </form>
              )}

              {stage.applications?.map((app, i) => {
                  const stageColors = { browsing: 'bg-muted text-muted-foreground', preparing: 'bg-secondary text-foreground/70', contacting: 'bg-[#E8F0EC] text-[#2F5233]',
                    applying: 'bg-[#F0EDF7] text-[#5B4D7D]', exam: 'bg-[#FDF2E6] text-[#8C6D41]',
                    waiting: 'bg-[#F9F1E7] text-[#8C6D41]', decided: 'bg-[#E8F0EC] text-[#2F5233]' };
                  const profStatusColors = { pending: 'text-muted-foreground', sent: 'text-[#5B6D8A]',
                    replied: 'text-[#3D6B52]', rejected: 'text-[#C4655A]', no_reply: 'text-[#D4A853]',
                    interview: 'text-[#4A7C8C]' };
                  const profStatusLabel = { pending: '待联系', sent: '已发信', replied: '已回复',
                    rejected: '婉拒', no_reply: '超期未回', interview: '获面试' };
                  return (
                    <Card key={i}>
<CardContent className="p-3">
                      {/* Header: school + stage + delete */}
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-semibold text-gray-800 truncate max-w-[130px]" title={app.school}>
                          {app.school}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${stageColors[app.stage_id] || 'bg-gray-100 text-gray-600'}`}>
                            {app.label}
                          </span>
                          <Button onClick={() => setDeleteTarget(app.school)} variant="ghost" size="icon"
                            className="text-muted-foreground hover:text-red-500 h-5 w-5" title="删除">&times;</Button>
                        </div>
                      </div>

                      {/* Progress mini-bar */}
                      <div className="h-1 bg-gray-100 rounded-full mb-1.5 overflow-hidden">
                        <div className="h-full bg-indigo-400 rounded-full transition-all"
                          style={{ width: `${(app.progress || 0) * 100}%` }}></div>
                      </div>

                      {/* Professors — click to cycle status */}
                      {app.professors?.length > 0 && (
                        <div className="text-xs text-gray-500 mb-1 flex flex-wrap items-center gap-1">
                          {app.professors.map((p, j) => {
                            const nextStatus = { pending: 'sent', sent: 'replied', replied: 'interview', interview: 'rejected', rejected: 'no_reply', no_reply: 'pending' };
                            return (
                              <span key={j} className={`inline-flex items-center gap-0.5 px-1 py-0.5 rounded ${profStatusColors[p.status] || 'text-gray-400'} bg-white border cursor-pointer hover:shadow`}
                                onClick={() => {
                                  const profs = app.professors.map((x, xi) => xi === j ? { ...x, status: nextStatus[x.status] || 'sent' } : x);
                                  updateApplication(app.school, { professors: profs });
                                }}
                                title="点击切换状态">
                                {p.name}({profStatusLabel[p.status] || p.status})
                                <button onClick={e => {
                                  e.stopPropagation();
                                  setSelectedProf({ school: app.school, professorName: p.name });
                                }} className="ml-0.5 text-gray-300 hover:text-indigo-500 align-middle" title="生成套磁邮件草稿">
                                  <FileText size={10} />
                                </button>
                                <span className="text-gray-300 hover:text-red-400 ml-0.5" onClick={e => {
                                  e.stopPropagation();
                                  const profs = app.professors.filter((_, xi) => xi !== j);
                                  updateApplication(app.school, { professors: profs });
                                }}>&times;</span>
                              </span>
                            );
                          })}
                        </div>
                      )}

                      {/* Official deadlines — locked, non-deletable */}
                      {(app.official_deadlines && (Array.isArray(app.official_deadlines) ? app.official_deadlines.length > 0 : Object.keys(app.official_deadlines).length > 0)) && (
                        <div className="text-xs text-muted-foreground mb-1 flex flex-wrap gap-1">
                          {Array.isArray(app.official_deadlines) ? (
                            app.official_deadlines.map((item, j) => (
                              <span key={j} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-muted border border-border"
                                title="官方截止日（不可编辑）">
                                <span className="text-[10px]">[锁]</span> {item.name}: {item.date || (item.start ? `${item.start.slice(0,10)}~${item.end ? item.end.slice(0,10) : ''}` : item.raw || '')}
                              </span>
                            ))
                          ) : (
                            Object.entries(app.official_deadlines).map(([k, v], j) => (
                              <span key={j} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-muted border border-border"
                                title="官方截止日（不可编辑）">
                                <span className="text-[10px]">[锁]</span> {k}: {v}
                              </span>
                            ))
                          )}
                        </div>
                      )}
                      {/* User-added deadlines — clickable to delete */}
                      {(app.deadlines && (Array.isArray(app.deadlines) ? app.deadlines.length > 0 : Object.keys(app.deadlines).length > 0)) && (
                        <div className="text-xs text-muted-foreground mb-1 flex flex-wrap gap-1">
                          {Array.isArray(app.deadlines) ? (
                            app.deadlines.map((item, j) => (
                              <span key={j} className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-muted border border-border cursor-pointer hover:bg-accent"
                                onClick={() => {
                                  const dl = [...app.deadlines];
                                  dl.splice(j, 1);
                                  updateApplication(app.school, { deadlines: dl });
                                }} title="点击删除">
                                {item.name}: {item.date || (item.start ? `${item.start.slice(0,10)}~${item.end ? item.end.slice(0,10) : ''}` : item.raw || '')}
                                <span className="text-muted-foreground/50">&times;</span>
                              </span>
                            ))
                          ) : (
                            Object.entries(app.deadlines).map(([k, v], j) => (
                              <span key={j} className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-muted border border-border cursor-pointer hover:bg-accent"
                                onClick={() => {
                                  const dl = { ...app.deadlines };
                                  delete dl[k];
                                  updateApplication(app.school, { deadlines: dl });
                                }} title="点击删除">
                                {k}: {v}
                                <span className="text-muted-foreground/50">&times;</span>
                              </span>
                            ))
                          )}
                        </div>
                      )}
                      {/* Notes — click to edit */}
                      {editCard === app.school + '-notes' ? (
                        <div className="flex gap-1 mb-1">
                          <Input value={editNotes} onChange={e => setEditNotes(e.target.value)}
                            className="flex-1 text-xs p-1 border rounded" placeholder="备注..." autoFocus
                            onKeyDown={e => { if (e.key === 'Enter') { updateApplication(app.school, { notes: editNotes }); setEditCard(null); } }} />
                          <Button onClick={() => { updateApplication(app.school, { notes: editNotes }); setEditCard(null); }}
                            className="text-xs px-1.5 bg-primary/100 text-white rounded">保存</Button>
                        </div>
                      ) : (
                        <div className="text-xs text-gray-400 italic truncate mb-1 cursor-pointer hover:text-indigo-500"
                          onClick={() => { setEditCard(app.school + '-notes'); setEditNotes(app.notes || ''); }}>
                          {app.notes || '+ 备注'}
                        </div>
                      )}

                      {/* Add professor */}
                      {editCard === app.school + '-prof' ? (
                        <div className="flex gap-1 mb-1 items-center">
                          <Input value={editProfName} onChange={e => setEditProfName(e.target.value)}
                            className="flex-1 text-xs p-1 border rounded" placeholder="教授姓名" autoFocus />
                          <Select value={editProfStatus} onChange={e => setEditProfStatus(e.target.value)}
                            className="text-xs p-1 border rounded w-16">
                            <option value="sent">已发信</option>
                            <option value="pending">待联系</option>
                            <option value="replied">已回复</option>
                            <option value="rejected">婉拒</option>
                            <option value="no_reply">无回复</option>
                            <option value="interview">获面试</option>
                          </Select>
                          <Button onClick={() => {
                            if (editProfName.trim()) {
                              const profs = [...(app.professors || []), { name: editProfName.trim(), status: editProfStatus, date: new Date().toISOString().slice(0, 10) }];
                              updateApplication(app.school, { professors: profs });
                              setEditCard(null); setEditProfName('');
                            }
                          }}
                            className="text-xs px-1.5 bg-primary/100 text-white rounded">保存</Button>
                        </div>
                      ) : (
                        <Button onClick={() => { setEditCard(app.school + '-prof'); setEditProfName(''); setEditProfStatus('sent'); }}
                          className="text-xs text-gray-400 hover:text-indigo-500 mb-1">+ 教授</Button>
                      )}

                      {/* Add deadline */}
                      {editCard === app.school + '-dl' ? (
                        <div className="flex gap-1 mb-1">
                          <Input value={editDeadlineKey} onChange={e => setEditDeadlineKey(e.target.value)}
                            className="w-20 text-xs p-1 border rounded" placeholder="如：出願締切" autoFocus />
                          <input type="date" value={editDeadlineVal} onChange={e => setEditDeadlineVal(e.target.value)}
                            className="flex-1 text-xs p-1 border rounded" />
                          <Button onClick={() => {
                            if (editDeadlineKey.trim() && editDeadlineVal.trim()) {
                              const dl = { ...(app.deadlines || {}), [editDeadlineKey.trim()]: editDeadlineVal.trim() };
                              updateApplication(app.school, { deadlines: dl });
                              setEditCard(null); setEditDeadlineKey(''); setEditDeadlineVal('');
                            }
                          }}
                            className="text-xs px-1.5 bg-primary/100 text-white rounded">保存</Button>
                        </div>
                      ) : (
                        <Button onClick={() => { setEditCard(app.school + '-dl'); setEditDeadlineKey(''); setEditDeadlineVal(''); }}
                          className="text-xs text-gray-400 hover:text-indigo-500 mb-1">+ 截止日</Button>
                      )}

                      {/* Stage buttons */}
                      {(app.next_stages?.length > 0 || app.prev_stages?.length > 0) && (
                        <div className="flex flex-wrap gap-1 mt-1.5 pt-1.5 border-t border-gray-50">
                          {app.prev_stages?.map(s => {
                            const key = 'back-' + s + app.school;
                            const label = s === 'contacting' ? '套磁' : s === 'applying' ? '出愿' : s === 'exam' ? '考试' : s === 'waiting' ? '等待' : s === 'decided' ? '确定' : s === 'preparing' ? '准备' : s;
                            return (
                              <Button key={s} onClick={() => advanceStage(s, app.school)}
                                disabled={advancing === key}
                                className="text-xs px-1.5 py-0.5 rounded bg-amber-50 hover:bg-amber-100 text-amber-600 transition disabled:opacity-30">
                                {advancing === key ? '...' : `← ${label}`}
                              </Button>
                            );
                          })}
                          {app.next_stages?.map(s => {
                            const key = s + app.school;
                            const label = s === 'contacting' ? '套磁' : s === 'applying' ? '出愿' : s === 'exam' ? '考试' : s === 'waiting' ? '等待' : s === 'decided' ? '确定' : s;
                            return (
                              <Button key={s} onClick={() => advanceStage(s, app.school)}
                                disabled={advancing === key}
                                className="text-xs px-1.5 py-0.5 rounded bg-gray-100 hover:bg-indigo-100 text-gray-600 hover:text-indigo-700 transition disabled:opacity-30">
                                {advancing === key ? '...' : label}
                              </Button>
                            );
                          })}
                        </div>
                      )}

                      {/* Timeline */}
                      {app.timeline?.length > 0 && (
                        <details className="mt-1">
                          <summary className="text-xs text-gray-400 cursor-pointer">时间线</summary>
                          <div className="mt-1 space-y-0.5">
                            {app.timeline.map((t, j) => (
                              <div key={j} className={`text-xs flex justify-between ${t.stage === app.stage_id ? 'font-medium text-primary' : 'text-gray-400'}`}>
                                <span>{t.label}</span>
                                <span>{t.start} ~ {t.end}</span>
                              </div>
                            ))}
                          </div>
                        </details>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            {/* All reminders (per-school + per-professor) */}
            {stage.all_reminders?.length > 0 && (
              <div className="mt-2 space-y-1">
                {stage.all_reminders.map((r, i) => (
                  <div key={i} className="text-xs text-amber-600 bg-amber-50 p-1.5 rounded">
                    {r.school ? `[${r.school}] ` : ''}{r.message}
                  </div>
                ))}
              </div>
            )}

            {/* Fallback: single-stage reminders (backward compat) */}
            {(!stage.all_reminders || stage.all_reminders.length === 0) && stage.reminders?.length > 0 && (
              <div className="mt-2 space-y-1">
                {stage.reminders.map((r, i) => (
                  <div key={i} className="text-xs text-amber-600 bg-amber-50 p-1.5 rounded">{r}</div>
                ))}
              </div>
            )}

            {/* Single-stage advance / rollback buttons (backward compat, when no applications) */}
            {(!stage.applications || stage.applications.length === 0) && (stage.next_stages?.length > 0 || stage.prev_stages?.length > 0) && (
              <div className="mt-2 flex flex-wrap gap-1">
                {stage.prev_stages?.map(s => {
                  const label = s === 'contacting' ? '套磁' : s === 'applying' ? '出愿' : s === 'exam' ? '考试' : s === 'waiting' ? '等待' : s === 'decided' ? '确定' : s === 'preparing' ? '准备' : s;
                  return (
                    <Button key={'back-' + s} onClick={() => advanceStage(s)}
                      disabled={advancing === s}
                      className="text-xs px-2 py-1 rounded bg-amber-50 hover:bg-amber-100 text-amber-600 transition disabled:opacity-30 disabled:cursor-wait">
                      {advancing === s ? '处理中...' : `← 回退「${label}」`}
                    </Button>
                  );
                })}
                {stage.next_stages?.map(s => {
                  const label = s === 'contacting' ? '套磁' : s === 'applying' ? '出愿' : s === 'exam' ? '考试' : s === 'waiting' ? '等待' : s === 'decided' ? '确定' : s;
                  return (
                    <Button key={s} onClick={() => advanceStage(s)}
                      disabled={advancing === s}
                      className="text-xs px-2 py-1 rounded bg-gray-100 hover:bg-indigo-100 text-gray-600 hover:text-indigo-700 transition disabled:opacity-30 disabled:cursor-wait">
                      {advancing === s ? '处理中...' : `进入「${label}」`}
                    </Button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <div className="p-4 border-b">
          <Button onClick={() => setShowProfile(true)}
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-primary w-full p-2 rounded-lg hover:bg-gray-50">
            <Settings size={16} /> 学生背景
          </Button>
          {profile && (
            <div className="mt-2 text-xs text-gray-500 space-y-1">
              <div>JLPT: {profile.jlpt_level} | 英语: {profile.english_score || '-'}</div>
              {profile.gpa_score > 0 && <div>GPA: {profile.gpa_score}/{profile.gpa_scale}</div>}
              <div>专业: {profile.target_major || '未设定'}</div>
              {profile.research_area && <div>方向: {profile.research_area}</div>}
            </div>
          )}
        </div>

        </div>{/* end scrollable area */}

        <div className="p-2 border-t border-border shrink-0 flex justify-center">
          <Button onClick={handleLogout} variant="ghost" size="icon"
            className="text-muted-foreground hover:text-red-500" title="退出">
            <LogOut size={15} />
          </Button>
        </div>
        </div>
      </aside>

      {/* Main area */}
      <main className="flex-1 flex flex-col">
        {/* Tab bar */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="border-b border-border bg-card px-4">
          <div className="flex items-center">
            <TabsList className="flex-1 justify-start gap-0 bg-transparent p-0 h-auto rounded-none">
              <TabsTrigger value="home" className="gap-2 text-sm data-[state=active]:border-b-2 data-[state=active]:border-foreground rounded-none data-[state=active]:shadow-none border-b-2 border-transparent -mb-[2px]">
                <LayoutGrid size={15} /> 首页
              </TabsTrigger>
              <TabsTrigger value="chat" className="gap-2 text-sm data-[state=active]:border-b-2 data-[state=active]:border-foreground rounded-none data-[state=active]:shadow-none border-b-2 border-transparent -mb-[2px]">
                <MessageCircle size={15} /> 对话
              </TabsTrigger>
              <TabsTrigger value="plaza" className="gap-2 text-sm data-[state=active]:border-b-2 data-[state=active]:border-foreground rounded-none data-[state=active]:shadow-none border-b-2 border-transparent -mb-[2px]">
                <LayoutGrid size={15} /> 广场
              </TabsTrigger>
              <TabsTrigger value="calendar" className="gap-2 text-sm data-[state=active]:border-b-2 data-[state=active]:border-foreground rounded-none data-[state=active]:shadow-none border-b-2 border-transparent -mb-[2px]">
                <Calendar size={15} /> 日历
              </TabsTrigger>
            </TabsList>
            <div className="shrink-0 flex items-center pr-1">
              <ReminderBell
                token={token}
                activeTab={activeTab}
                onOpenDrawer={handleOpenDrawer}
                onNewReminders={handleNewReminders}
              />
            </div>
          </div>
        </Tabs>

        <AnimatePresence mode="wait">
        {activeTab === 'home' ? (
          <DashboardView
            greeting={greeting}
            applications={stage?.applications}
            profile={profile}
            loading={greetingLoading}
            onNavigate={(tab, params) => {
              if (params?.filter) setPlazaFilter(params.filter);
              setActiveTab(tab);
            }}
            onEditProfile={() => setShowProfile(true)}
          />
        ) : activeTab === 'chat' ? (
        <>
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4">
          <AnimatePresence>
          {messages.map((msg, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-gray-700' : 'bg-indigo-600'}`}>
                {msg.role === 'user' ? <User size={14} className="text-white" /> : <Bot size={14} className="text-white" />}
              </div>
              <div className={`max-w-[75%] ${msg.role === 'user' ? 'bg-foreground text-white' : 'bg-white border border-border shadow-sm'} p-4 rounded-2xl text-sm leading-relaxed`}>
                {msg.content && <div className="whitespace-pre-wrap" dangerouslySetInnerHTML={{
                  __html: msg.content
                    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>')
                    .replace(/### (.+)/g, '<h4 class="font-semibold text-sm mt-2 mb-1">$1</h4>')
                    .replace(/- (.+)/g, '<span class="block ml-2">· $1</span>')
                }} />}
                {msg.navSuggestion && (
                  <div className="bg-primary/10 border border-indigo-200 rounded-xl p-3">
                    <p className="text-sm text-gray-700 mb-2">{msg.navSuggestion.prompt || '一起去选校广场看看？'}</p>
                    <div className="flex gap-2">
                      <Button onClick={() => {
                        setPlazaFilter(msg.navSuggestion.filter || '');
                        setActiveTab('plaza');
                        setMessages(prev => prev.map(m => m.navSuggestion ? { ...m, navSuggestion: null, content: '已跳转到广场' } : m));
                      }}
                        className="text-xs px-3 py-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-indigo-700 transition font-medium">
                        去看看
                      </Button>
                      <Button onClick={() => {
                        setMessages(prev => prev.map(m => m.navSuggestion ? { ...m, navSuggestion: null, content: '' } : m));
                      }}
                        className="text-xs px-3 py-1.5 rounded-lg bg-white border text-gray-500 hover:bg-gray-50 transition">
                        不了
                      </Button>
                    </div>
                  </div>
                )}
                {msg.suggestedSchools && (() => {
                  const trackedNames = (stage?.applications || []).map(a => a.school);
                  const filtered = msg.suggestedSchools.filter(s => !trackedNames.includes(s));
                  if (filtered.length === 0) return null;
                  return (
                  <div>
                    <p className="text-gray-600 mb-2">要将这些学校加入申请追踪吗？</p>
                    <div className="flex flex-wrap gap-2">
                      {filtered.map(school => (
                        <Button key={school} onClick={async () => {
                          try {
                            await apiCall('/v1/applications', token, { method: 'POST', body: { school } });
                            const updated = await apiCall('/v1/stage', token);
                            setStage(updated);
                            setMessages(prev => prev.map(m => m.suggestedSchools ? { ...m, suggestedSchools: null, content: `已添加「${school}」到追踪列表` } : m));
                          } catch (err) { showToast(`添加失败: ${err.message}`); }
                        }}
                          className="text-xs px-3 py-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-indigo-700 transition font-medium">
                          + {school}
                        </Button>
                      ))}
                    </div>
                  </div>
                  );
                })()}
              </div>
            </motion.div>
          ))}
          </AnimatePresence>
          {loading && (
            <div className="flex items-center gap-2 text-gray-400 text-sm ml-11">
              <Loader2 size={14} className="animate-spin" /> 思考中...
            </div>
          )}
        </div>
        </>
        ) : activeTab === 'plaza' ? (
        /* Plaza view */
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-5xl mx-auto">
            <h2 className="text-lg font-bold text-gray-800 mb-1">学校广场</h2>
            <p className="text-sm text-gray-400 mb-4">浏览学校信息，找到感兴趣的加入追踪</p>
            <div className="flex items-center gap-2 mb-4">
              <Input value={plazaFilter} onChange={e => setPlazaFilter(e.target.value)}
                placeholder="筛选专业，如：情报理工、NLP..."
                className="flex-1 max-w-md p-2.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              {plazaFilter && (
                <span className="text-xs text-primary bg-primary/10 px-2 py-1 rounded-full whitespace-nowrap">
                  {catalog.filter(s => schoolMatches(s, plazaFilter)).length} 条结果
                  <Button onClick={() => setPlazaFilter('')} className="ml-1 text-gray-400 hover:text-gray-600">&times;</Button>
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {(() => {
                const filtered = catalog.filter(s => schoolMatches(s, plazaFilter));
                if (filtered.length === 0 && plazaFilter) {
                  return <div className="col-span-2 text-center py-12 text-gray-400">
                    <p className="text-lg mb-2">没有完全匹配的学校</p>
                    <p className="text-sm">试试换个说法，或者 <Button onClick={() => setPlazaFilter('')} className="text-indigo-500 underline">清除筛选</Button> 查看全部</p>
                  </div>;
                }
                return filtered.map((s, i) => {
                  const trackedSchools = (stage?.applications || []).map(a => a.school);
                  const alreadyTracked = trackedSchools.includes(s.name);
                  return (
                <Card key={i} data-testid="school-card">
<CardContent className="p-5">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-sm font-semibold text-gray-800 school-name">{s.name}</h3>
                    <Button onClick={async () => {
                      if (alreadyTracked) return;
                      try {
                        await apiCall('/v1/applications', token, { method: 'POST', body: { school: s.name, major: s.majors?.[0] || '', official_deadlines: s.deadlines, notes: s.notes } });
                        const updated = await apiCall('/v1/stage', token);
                        setStage(updated);
                        showToast(`已添加「${s.name}」`, 'success');
                      } catch (err) { showToast(`添加失败: ${err.message}`); }
                    }}
                      disabled={alreadyTracked}
                      className={`text-xs px-2.5 py-1 rounded-lg transition font-medium shrink-0 ${alreadyTracked ? 'bg-gray-100 text-gray-400' : 'bg-primary/10 hover:bg-indigo-100 text-primary'}`}>
                      {alreadyTracked ? '已追踪' : '追踪'}
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-1 mb-2 school-majors">
                    {s.majors?.map(m => (
                      <span key={m} className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">{m}</span>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-1 mb-2 school-tags">
                    {s.tags?.map(t => (
                      <span key={t} className="text-xs px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-500">{t}</span>
                    ))}
                  </div>
                  <div className="text-xs text-gray-400 space-y-0.5 mb-2">
                    <div>JLPT: {s.jlpt_min || s.jlpt || '不要求'} | 英语: {s.english_req ? (s.english_req.required ? (s.english_req.min ? s.english_req.type+' '+s.english_req.min : s.english_req.type || '必要') : '不要求') : s.english || '-'} | 考试: {s.exam}</div>
                  </div>
                  <details className="text-xs">
                    <summary className="text-gray-400 cursor-pointer">截止日期</summary>
                    <div className="mt-1 space-y-0.5 text-gray-500">
                      {Array.isArray(s.deadlines) ? (
                        s.deadlines.map((item, idx) => (
                          <div key={idx} className="flex justify-between">
                            <span>{item.name}</span>
                            <span>{item.date || (item.start && item.end ? `${item.start.slice(0,10)} ~ ${item.end.slice(0,10)}` : item.raw || '')}</span>
                          </div>
                        ))
                      ) : (
                        Object.entries(s.deadlines || {}).map(([k, v]) => (
                          <div key={k} className="flex justify-between"><span>{k}</span><span>{v}</span></div>
                        ))
                      )}
                    </div>
                  </details>
                  {s.notes && <div className="text-xs text-gray-400 mt-2 italic">{s.notes}</div>}
                  <div className="text-[10px] text-gray-400 mt-2 flex items-center justify-between">
                    {s.website ? (
                      <a href={s.website} target="_blank" rel="noopener noreferrer"
                        className="text-indigo-500 hover:underline truncate max-w-[180px]"
                        onClick={e => e.stopPropagation()}>
                        官网 →
                      </a>
                    ) : <span />}
                    {s.updated_at && (
                      <span className="tabular-nums">更新: {s.updated_at.slice(0, 10)}</span>
                    )}
                  </div>
                </CardContent>
              </Card>
              )});
              })()}
            </div>
          </div>
        </div>
        ) : (
        /* Calendar view */
        <CalendarView applications={stage?.applications} />
        )}

        </AnimatePresence>
        {/* Always-visible chat input */}
        <div className={`border-t border-border bg-card shrink-0 transition-all duration-200 ${inputOpen ? 'p-3' : 'p-1'}`}>
          {!inputOpen && (
            <div className="flex justify-center">
              <Button variant="ghost" size="icon" onClick={() => setInputOpen(true)} title="展开输入框">
                <Send size={14} />
              </Button>
            </div>
          )}
          <div className={inputOpen ? '' : 'hidden'}>
          <div className="max-w-3xl mx-auto flex gap-2">
            <Input value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendMessage()} disabled={loading}
              placeholder={activeTab === 'plaza' ? '在广场筛选学校...' : activeTab === 'calendar' ? '问日历相关的问题...' : '输入你的留学疑问...'}
              className="flex-1 p-2.5 bg-muted border-0 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-[#B0AFAD] placeholder:text-muted-foreground" />
            <Button onClick={sendMessage} disabled={loading || !input.trim()}
              className="w-10 h-10 flex items-center justify-center bg-foreground text-white rounded-xl hover:bg-foreground/80 disabled:opacity-30 transition shrink-0">
              <Send size={15} />
            </Button>
            <Button onClick={() => { if (input.trim()) { setPlazaFilter(input.trim()); setActiveTab('plaza'); } }}
              disabled={!input.trim()}
              className="w-10 h-10 flex items-center justify-center bg-muted text-muted-foreground rounded-xl hover:bg-[#ECEBE8] hover:text-foreground/70 disabled:opacity-30 transition shrink-0"
              title="在广场搜索学校">
              <Search size={15} />
            </Button>
            <Button variant="ghost" size="icon" onClick={() => setInputOpen(false)} title="收起输入框" className="shrink-0">
              <LayoutGrid size={12} />
            </Button>
          </div>
        </div>
        </div>{/* close input hidden wrapper */}
        {/* Mini chat panel in plaza/calendar — shows latest messages */}
        {activeTab !== 'chat' && messages.length > 0 && (
          <div className="border-t bg-white px-4 py-2 max-h-32 overflow-y-auto shrink-0">
            {messages.slice(-3).map((msg, i) => (
              <div key={i} className={`text-xs mb-1 ${msg.role === 'user' ? 'text-gray-500' : 'text-gray-700'}`}>
                <span className="font-medium">{msg.role === 'user' ? '你: ' : '顾问: '}</span>
                <span className="whitespace-pre-wrap line-clamp-2">{(msg.content || '').slice(0, 150)}</span>
              </div>
            ))}
            <Button onClick={() => setActiveTab('chat')} className="text-xs text-indigo-500 hover:underline mt-1">
              查看完整对话 →
            </Button>
          </div>
        )}
      </main>

      {/* Reminder Drawer */}
      <ReminderDrawer
        open={drawerOpen}
        onClose={handleDrawerClose}
        reminders={drawerData.reminders}
        loading={drawerData.loading}
        error={drawerData.error}
        onRefresh={drawerData.onRefresh}
        token={token}
        onAction={handleReminderAction}
      />

      {/* Profile slide-out panel */}
      {showProfile && <div className="fixed inset-0 z-50 flex justify-end" onClick={() => setShowProfile(false)}>
        <div className="absolute inset-0 bg-black/30" />
        <div className="relative w-full max-w-md bg-background h-full overflow-y-auto shadow-xl animate-slide-in" onClick={e => e.stopPropagation()}>
          <div className="p-4 border-b flex items-center justify-between sticky top-0 bg-background z-10">
            <h2 className="text-lg font-semibold">学生背景</h2>
            <Button variant="ghost" size="icon" onClick={() => setShowProfile(false)}>&times;</Button>
          </div>
          <form onSubmit={saveProfile} className="p-4 space-y-3 text-sm">
            <label className="block text-xs text-muted-foreground">日语等级</label>
            <Select name="jlpt_level" defaultValue={profile?.jlpt_level || '无'}
              className="w-full p-2 border rounded">
              {['无','N5','N4','N3','N2','N1'].map(l => <option key={l}>{l}</option>)}
            </Select>
            <label className="block text-xs text-muted-foreground">英语成绩</label>
            <Input name="english_score" defaultValue={profile?.english_score || ''}
              placeholder="TOEFL 95 / TOEIC 750" className="w-full p-2 border rounded" />
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="block text-xs text-muted-foreground">GPA</label>
                <Input name="gpa_score" type="number" step="0.1" defaultValue={profile?.gpa_score || ''}
                  placeholder="3.5" className="w-full p-2 border rounded" />
              </div>
              <div className="w-20">
                <label className="block text-xs text-muted-foreground">满分</label>
                <Select name="gpa_scale" defaultValue={profile?.gpa_scale || 4.0}
                  className="w-full p-2 border rounded">
                  {[4.0, 4.3, 5.0, 100].map(s => <option key={s} value={s}>{s}</option>)}
                </Select>
              </div>
            </div>
            <label className="block text-xs text-muted-foreground">目标专业</label>
            <Input name="target_major" defaultValue={profile?.target_major || ''}
              placeholder="如：情报理工" className="w-full p-2 border rounded" />
            <label className="block text-xs text-muted-foreground">研究方向</label>
            <Input name="research_area" defaultValue={profile?.research_area || ''}
              placeholder="如：自然语言处理" className="w-full p-2 border rounded" />
            <label className="block text-xs text-muted-foreground">本科院校</label>
            <Input name="undergraduate_school" defaultValue={profile?.undergraduate_school || ''}
              placeholder="如：深圳大学" className="w-full p-2 border rounded" />
            <Button type="submit" className="w-full" size="sm">保存</Button>
          </form>
        </div>
      </div>}

      {/* Delete confirmation Dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              确定要移除「{deleteTarget}」吗？该操作不会删除已记录的数据，但会从追踪列表中移除。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>取消</Button>
            <Button variant="destructive" onClick={removeSchool}>确认删除</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <OutreachDraft
        open={!!selectedProf}
        onClose={() => setSelectedProf(null)}
        school={selectedProf?.school || ''}
        professorName={selectedProf?.professorName || ''}
        token={token}
      />
    </div>
  );
}
