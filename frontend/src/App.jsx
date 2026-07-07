import { useState, useEffect, useRef } from 'react';
import { Send, User, Bot, Loader2, LogOut, Settings, LayoutGrid, MessageCircle, Calendar, Search } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';

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
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export default function App() {
  // ── Auth state ──
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState('login'); // login | register
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  // ── Toast ──
  const [toast, setToast] = useState(null); // {text, type: 'error'|'success'}
  const showToast = (text, type = 'error') => {
    setToast({ text, type });
    setTimeout(() => setToast(null), 4000);
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
      apiCall('/v1/schools', token).then(r => setCatalog(r.schools)).catch(() => {});
    }
  }, [token]);

  // ── Scroll to bottom ──
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    localStorage.setItem('chat_v2', JSON.stringify(messages.slice(-100)));
  }, [messages]);

  // ── Greeting helper ──
  const loadGreeting = async (t) => {
    try {
      const g = await apiCall('/v1/greeting', t);
      setMessages([{ role: 'assistant', content: g.message }]);
    } catch {
      setMessages([{ role: 'assistant', content: '欢迎回来！我是你的日本升学顾问，请告诉我你的目标。' }]);
    }
  };

  // ── Auth handlers ──
  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const r = await loginSupabase(email, password);
      setToken(r.token);
      setUser(r.user || { email });
      await loadGreeting(r.token);
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
  // ── Plaza state ──
  const [activeTab, setActiveTab] = useState('chat'); // chat | plaza | calendar
  const [catalog, setCatalog] = useState([]);
  const [plazaFilter, setPlazaFilter] = useState('');
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

  const removeSchool = async (school) => {
    if (!confirm(`确认删除「${school}」？`)) return;
    try {
      await apiCall(`/v1/applications?school=${encodeURIComponent(school)}`, token, { method: 'DELETE' });
      const updated = await apiCall('/v1/stage', token);
      setStage(updated);
    } catch (err) {
      showToast(`删除失败: ${err.message}`);
    }
  };

  const updateApplication = async (school, updates) => {
    try {
      await apiCall('/v1/applications', token, { method: 'POST', body: { school, ...updates } });
      const updated = await apiCall('/v1/stage', token);
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

    try {
      const res = await fetch(`${API}/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ query: input }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';
      let suggested = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const lines = decoder.decode(value, { stream: true }).split('\n');
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const parsed = JSON.parse(line.slice(6));
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
          } catch {}
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
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md">
          <h1 className="text-2xl font-bold text-gray-800 mb-6">日本升学顾问</h1>
          <div className="flex gap-2 mb-6">
            <Button
              onClick={() => setAuthMode('login')}
              variant={authMode === 'login' ? 'default' : 'secondary'}
              className="flex-1"
            >登录</Button>
            <Button
              onClick={() => setAuthMode('register')}
              variant={authMode === 'register' ? 'default' : 'secondary'}
              className="flex-1"
            >注册</Button>
          </div>
          <form onSubmit={authMode === 'login' ? handleLogin : handleRegister} className="space-y-3">
            <Input type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="邮箱" required />
            <Input type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="密码" required minLength={6} />
            <Button type="submit" className="w-full">
              {authMode === 'login' ? '登录' : '注册'}
            </Button>
          </form>
        </div>
      </div>
    );
  }

  // ── Main app ──
  return (
    <div className="flex h-screen bg-background">
      {/* Toast notification */}
      {toast && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 animate-[fadeIn_0.2s_ease-out]">
          <div className={`px-4 py-2 rounded-lg shadow-lg text-sm font-medium ${
            toast.type === 'error' ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'
          }`}>
            {toast.text}
          </div>
        </div>
      )}
      {/* Sidebar */}
      <aside className="w-80 bg-white border-r border-border flex flex-col shrink-0 overflow-hidden">
        <div className="p-5 border-b border-border">
          <h1 className="text-lg font-bold text-foreground tracking-tight">升学顾问</h1>
          <p className="text-[11px] text-muted-foreground mt-0.5">{user?.email}</p>
        </div>

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
                <form onSubmit={addSchool} className="border rounded-lg p-2.5 bg-primary/10/50 space-y-1.5">
                  <Input value={newSchool} onChange={e => setNewSchool(e.target.value)}
                    placeholder="学校名称，如：京都大学 情报理工"
                    className="w-full text-xs p-2 border rounded focus:outline-none focus:ring-1 focus:ring-indigo-400" autoFocus />
                  <select value={newSchoolStage} onChange={e => setNewSchoolStage(e.target.value)}
                    className="w-full text-xs p-2 border rounded focus:outline-none focus:ring-1 focus:ring-indigo-400">
                    <option value="browsing">关注中</option>
                    <option value="preparing">准备阶段</option>
                    <option value="contacting">套磁阶段</option>
                    <option value="applying">出愿阶段</option>
                    <option value="exam">考试阶段</option>
                    <option value="waiting">等待结果</option>
                    <option value="decided">确定去向</option>
                  </select>
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
                    <Card key={i} className="card-float">
<CardContent className="p-3">
                      {/* Header: school + stage + delete */}
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-semibold text-gray-800 truncate max-w-[130px]" title={app.school}>
                          {app.school}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${stageColors[app.stage_id] || 'bg-gray-100 text-gray-600'}`}>
                            {app.label}
                          </span>
                          <Button onClick={() => removeSchool(app.school)}
                            className="text-gray-300 hover:text-red-400 text-xs leading-none transition" title="删除">&times;</Button>
                        </div>
                      </div>

                      {/* Progress mini-bar */}
                      <div className="h-1 bg-gray-100 rounded-full mb-1.5 overflow-hidden">
                        <div className="h-full bg-indigo-400 rounded-full transition-all"
                          style={{ width: `${(app.progress || 0) * 100}%` }}></div>
                      </div>

                      {/* Professors — click to cycle status */}
                      {app.professors?.length > 0 && (
                        <div className="text-[10px] text-gray-500 mb-1 flex flex-wrap items-center gap-1">
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

                      {/* Deadlines — clickable to delete */}
                      {(app.deadlines && Object.keys(app.deadlines).length > 0) && (
                        <div className="text-[10px] text-gray-400 mb-1 flex flex-wrap gap-1">
                          {Object.entries(app.deadlines).map(([k, v], j) => (
                            <span key={j} className="inline-flex items-center gap-0.5 px-1 py-0.5 rounded bg-gray-50 border cursor-pointer hover:shadow"
                              onClick={() => {
                                const dl = { ...app.deadlines };
                                delete dl[k];
                                updateApplication(app.school, { deadlines: dl });
                              }} title="点击删除">
                              {k}: {v}
                              <span className="text-gray-300">&times;</span>
                            </span>
                          ))}
                        </div>
                      )}
                      {/* Notes — click to edit */}
                      {editCard === app.school + '-notes' ? (
                        <div className="flex gap-1 mb-1">
                          <Input value={editNotes} onChange={e => setEditNotes(e.target.value)}
                            className="flex-1 text-[10px] p-1 border rounded" placeholder="备注..." autoFocus
                            onKeyDown={e => { if (e.key === 'Enter') { updateApplication(app.school, { notes: editNotes }); setEditCard(null); } }} />
                          <Button onClick={() => { updateApplication(app.school, { notes: editNotes }); setEditCard(null); }}
                            className="text-[10px] px-1.5 bg-primary/100 text-white rounded">保存</Button>
                        </div>
                      ) : (
                        <div className="text-[10px] text-gray-400 italic truncate mb-1 cursor-pointer hover:text-indigo-500"
                          onClick={() => { setEditCard(app.school + '-notes'); setEditNotes(app.notes || ''); }}>
                          {app.notes || '+ 备注'}
                        </div>
                      )}

                      {/* Add professor */}
                      {editCard === app.school + '-prof' ? (
                        <div className="flex gap-1 mb-1 items-center">
                          <Input value={editProfName} onChange={e => setEditProfName(e.target.value)}
                            className="flex-1 text-[10px] p-1 border rounded" placeholder="教授姓名" autoFocus />
                          <select value={editProfStatus} onChange={e => setEditProfStatus(e.target.value)}
                            className="text-[10px] p-1 border rounded w-16">
                            <option value="sent">已发信</option>
                            <option value="pending">待联系</option>
                            <option value="replied">已回复</option>
                            <option value="rejected">婉拒</option>
                            <option value="no_reply">无回复</option>
                            <option value="interview">获面试</option>
                          </select>
                          <Button onClick={() => {
                            if (editProfName.trim()) {
                              const profs = [...(app.professors || []), { name: editProfName.trim(), status: editProfStatus, date: new Date().toISOString().slice(0, 10) }];
                              updateApplication(app.school, { professors: profs });
                              setEditCard(null); setEditProfName('');
                            }
                          }}
                            className="text-[10px] px-1.5 bg-primary/100 text-white rounded">保存</Button>
                        </div>
                      ) : (
                        <Button onClick={() => { setEditCard(app.school + '-prof'); setEditProfName(''); setEditProfStatus('sent'); }}
                          className="text-[10px] text-gray-400 hover:text-indigo-500 mb-1">+ 教授</Button>
                      )}

                      {/* Add deadline */}
                      {editCard === app.school + '-dl' ? (
                        <div className="flex gap-1 mb-1">
                          <Input value={editDeadlineKey} onChange={e => setEditDeadlineKey(e.target.value)}
                            className="w-20 text-[10px] p-1 border rounded" placeholder="如：出願締切" autoFocus />
                          <Input value={editDeadlineVal} onChange={e => setEditDeadlineVal(e.target.value)}
                            className="flex-1 text-[10px] p-1 border rounded" placeholder="如：2026-12-15" />
                          <Button onClick={() => {
                            if (editDeadlineKey.trim() && editDeadlineVal.trim()) {
                              const dl = { ...(app.deadlines || {}), [editDeadlineKey.trim()]: editDeadlineVal.trim() };
                              updateApplication(app.school, { deadlines: dl });
                              setEditCard(null); setEditDeadlineKey(''); setEditDeadlineVal('');
                            }
                          }}
                            className="text-[10px] px-1.5 bg-primary/100 text-white rounded">保存</Button>
                        </div>
                      ) : (
                        <Button onClick={() => { setEditCard(app.school + '-dl'); setEditDeadlineKey(''); setEditDeadlineVal(''); }}
                          className="text-[10px] text-gray-400 hover:text-indigo-500 mb-1">+ 截止日</Button>
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
                                className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 hover:bg-amber-100 text-amber-600 transition disabled:opacity-30">
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
                                className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 hover:bg-indigo-100 text-gray-600 hover:text-indigo-700 transition disabled:opacity-30">
                                {advancing === key ? '...' : label}
                              </Button>
                            );
                          })}
                        </div>
                      )}

                      {/* Timeline */}
                      {app.timeline?.length > 0 && (
                        <details className="mt-1">
                          <summary className="text-[10px] text-gray-400 cursor-pointer">时间线</summary>
                          <div className="mt-1 space-y-0.5">
                            {app.timeline.map((t, j) => (
                              <div key={j} className={`text-[10px] flex justify-between ${t.stage === app.stage_id ? 'font-medium text-primary' : 'text-gray-400'}`}>
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
          <Button onClick={() => setShowProfile(!showProfile)}
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-primary w-full p-2 rounded-lg hover:bg-gray-50">
            <Settings size={16} /> 学生背景
          </Button>
          {profile && (
            <div className="mt-2 text-xs text-gray-500 space-y-1">
              <div>JLPT: {profile.jlpt_level} | 英语: {profile.english_score || '-'}</div>
              {profile.gpa_score > 0 && <div>GPA: {profile.gpa_score}/{profile.gpa_scale}</div>}
              <div>专业: {profile.target_major || '未设定'}</div>
              {profile.research_area && <div>方向: {profile.research_area}</div>}
              {profile.facts && Object.keys(profile.facts).length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-primary">AI 已记录 ({Object.keys(profile.facts).length}条)</summary>
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
              <Input name="english_score" defaultValue={profile?.english_score || ''}
                placeholder="英语: TOEFL 95" className="w-full p-2 border rounded" />
              <div className="flex gap-2">
                <Input name="gpa_score" type="number" step="0.1" defaultValue={profile?.gpa_score || ''}
                  placeholder="GPA" className="w-1/2 p-2 border rounded" />
                <select name="gpa_scale" defaultValue={profile?.gpa_scale || 4.0}
                  className="w-1/2 p-2 border rounded">
                  {[4.0, 4.3, 5.0, 100].map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <Input name="target_major" defaultValue={profile?.target_major || ''}
                placeholder="目标专业" className="w-full p-2 border rounded" />
              <Input name="research_area" defaultValue={profile?.research_area || ''}
                placeholder="研究方向" className="w-full p-2 border rounded" />
              <Input name="undergraduate_school" defaultValue={profile?.undergraduate_school || ''}
                placeholder="本科院校" className="w-full p-2 border rounded" />
              <Button type="submit" className="w-full" size="sm">
                保存
              </Button>
            </form>
          </div>
        )}

        </div>{/* end scrollable area */}

        <div className="p-4 border-t shrink-0">
          <Button onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-red-500 w-full p-2">
            <LogOut size={16} /> 退出
          </Button>
        </div>
      </aside>

      {/* Main area */}
      <main className="flex-1 flex flex-col">
        {/* Tab bar */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="border-b border-border bg-card px-4">
          <TabsList className="w-full justify-start gap-0 bg-transparent p-0 h-auto rounded-none">
            <TabsTrigger value="chat" className="gap-2 text-[13px] data-[state=active]:border-b-2 data-[state=active]:border-foreground rounded-none data-[state=active]:shadow-none border-b-2 border-transparent -mb-[2px]">
              <MessageCircle size={15} /> 对话
            </TabsTrigger>
            <TabsTrigger value="plaza" className="gap-2 text-[13px] data-[state=active]:border-b-2 data-[state=active]:border-foreground rounded-none data-[state=active]:shadow-none border-b-2 border-transparent -mb-[2px]">
              <LayoutGrid size={15} /> 广场
            </TabsTrigger>
            <TabsTrigger value="calendar" className="gap-2 text-[13px] data-[state=active]:border-b-2 data-[state=active]:border-foreground rounded-none data-[state=active]:shadow-none border-b-2 border-transparent -mb-[2px]">
              <Calendar size={15} /> 日历
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {activeTab === 'chat' ? (
        <>
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4">
          <AnimatePresence>
          {messages.map((msg, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-gray-700' : 'bg-indigo-600'}`}>
                {msg.role === 'user' ? <User size={14} className="text-white" /> : <Bot size={14} className="text-white" />}
              </div>
              <div className={`max-w-[75%] ${msg.role === 'user' ? 'bg-foreground text-white' : msg.suggestedSchools || msg.navSuggestion ? 'bg-white border border-border card-float' : 'bg-white card-float'} p-4 rounded-2xl text-sm leading-relaxed`}>
                {msg.content && <div className="whitespace-pre-wrap">{msg.content}</div>}
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
                {msg.suggestedSchools && (
                  <div>
                    <p className="text-gray-600 mb-2">要将这些学校加入申请追踪吗？</p>
                    <div className="flex flex-wrap gap-2">
                      {msg.suggestedSchools.map(school => (
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
                )}
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
                  {catalog.filter(s => {
                    const text = JSON.stringify(s).toLowerCase();
                    const words = plazaFilter.split(/\s+/).filter(w => w.length > 0);
                    return words.some(w => text.includes(w.toLowerCase()));
                  }).length} 条结果
                  <Button onClick={() => setPlazaFilter('')} className="ml-1 text-gray-400 hover:text-gray-600">&times;</Button>
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {(() => {
                const filtered = catalog.filter(s => {
                  if (!plazaFilter) return true;
                  const text = JSON.stringify(s).toLowerCase();
                  const words = plazaFilter.split(/\s+/).filter(w => w.length > 0);
                  return words.some(w => text.includes(w.toLowerCase()));
                });
                if (filtered.length === 0 && plazaFilter) {
                  return <div className="col-span-2 text-center py-12 text-gray-400">
                    <p className="text-lg mb-2">没有完全匹配的学校</p>
                    <p className="text-sm">试试换个说法，或者 <Button onClick={() => setPlazaFilter('')} className="text-indigo-500 underline">清除筛选</Button> 查看全部</p>
                  </div>;
                }
                return filtered.map((s, i) => (
                <Card key={i} className="card-float">
<CardContent className="p-5">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-sm font-semibold text-gray-800">{s.name}</h3>
                    <Button onClick={async () => {
                      try {
                        await apiCall('/v1/applications', token, { method: 'POST', body: { school: s.name, deadlines: s.deadlines, notes: s.notes } });
                        const updated = await apiCall('/v1/stage', token);
                        setStage(updated);
                        showToast(`已添加「${s.name}」`, 'success');
                      } catch (err) { showToast(`添加失败: ${err.message}`); }
                    }}
                      className="text-xs px-2.5 py-1 rounded-lg bg-primary/10 hover:bg-indigo-100 text-primary transition font-medium shrink-0">
                      追踪
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-1 mb-2">
                    {s.majors?.map(m => (
                      <span key={m} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">{m}</span>
                    ))}
                  </div>
                  <div className="text-[10px] text-gray-400 space-y-0.5 mb-2">
                    <div>JLPT: {s.jlpt} | 英语: {s.english} | 考试: {s.exam}</div>
                  </div>
                  <details className="text-[10px]">
                    <summary className="text-gray-400 cursor-pointer">截止日期</summary>
                    <div className="mt-1 space-y-0.5 text-gray-500">
                      {Object.entries(s.deadlines || {}).map(([k, v]) => (
                        <div key={k} className="flex justify-between"><span>{k}</span><span>{v}</span></div>
                      ))}
                    </div>
                  </details>
                  {s.notes && <div className="text-[10px] text-gray-400 mt-2 italic">{s.notes}</div>}
                </CardContent>
              </Card>
              ));
              })()}
            </div>
          </div>
        </div>
        ) : (
        /* Calendar view */
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-5xl mx-auto">
            <h2 className="text-lg font-bold text-gray-800 mb-4">申请日历</h2>
            {!stage?.applications?.length ? (
              <p className="text-sm text-gray-400">还没有追踪的学校，去「广场」添加吧</p>
            ) : (() => {
              const now = new Date();
              const months = [];
              for (let i = -1; i <= 8; i++) {
                const d = new Date(now.getFullYear(), now.getMonth() + i, 1);
                months.push(d);
              }
              return (
                <div className="overflow-x-auto">
                  <div className="flex min-w-[800px]">
                    <div className="w-36 shrink-0">
                      <div className="h-8"></div>
                      {stage.applications.map((app, i) => (
                        <div key={i} className="h-16 flex items-center text-xs font-medium text-gray-700 border-b border-gray-50 pr-2 truncate">{app.school}</div>
                      ))}
                    </div>
                    <div className="flex-1 flex">
                      {months.map((m, mi) => {
                        const isCurrent = m.getMonth() === now.getMonth() && m.getFullYear() === now.getFullYear();
                        const mKey = `${m.getFullYear()}-${String(m.getMonth()+1).padStart(2,'0')}`;
                        return (
                          <div key={mi} className={`flex-1 min-w-[55px] border-l ${isCurrent ? 'bg-primary/10/40' : ''}`}>
                            <div className={`h-8 text-center text-[10px] pt-2 font-medium ${isCurrent ? 'text-primary' : 'text-gray-400'}`}>
                              {m.getMonth()+1}月
                            </div>
                            {stage.applications.map((app, ai) => {
                              const dots = [];
                              if (app.deadlines) {
                                Object.entries(app.deadlines).forEach(([k, v]) => {
                                  try {
                                    const ds = String(v).split(/[~～]/)[0].trim().replace(/[年月]/g,'-').replace(/[日]/g,'');
                                    const d = new Date(ds);
                                    if (!isNaN(d.getTime()) && d.getMonth() === m.getMonth() && d.getFullYear() === m.getFullYear()) {
                                      dots.push({ label: k, date: ds, type: 'deadline' });
                                    }
                                  } catch {}
                                });
                              }
                              return (
                                <div key={ai} className={`h-16 border-b border-gray-50 relative ${isCurrent ? '' : ''}`}>
                                  {dots.map((dot, di) => (
                                    <div key={di} className="absolute left-0.5 right-0.5 text-[8px] px-0.5 py-px rounded bg-red-100 text-red-700 truncate"
                                      style={{ top: `${2 + di * 16}px` }} title={`${dot.label}: ${dot.date}`}>
                                      {dot.label}
                                    </div>
                                  ))}
                                </div>
                              );
                            })}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 mt-3 text-[10px] text-gray-400">
                    <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-red-100 inline-block"></span> 截止日</span>
                    <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-primary/10 inline-block"></span> 本月</span>
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
        )}
        {/* Always-visible chat input */}
        <div className="p-3 border-t border-border bg-white shrink-0">
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
          </div>
        </div>
        {/* Mini chat panel in plaza/calendar — shows latest messages */}
        {activeTab !== 'chat' && messages.length > 0 && (
          <div className="border-t bg-white px-4 py-2 max-h-32 overflow-y-auto shrink-0">
            {messages.slice(-3).map((msg, i) => (
              <div key={i} className={`text-xs mb-1 ${msg.role === 'user' ? 'text-gray-500' : 'text-gray-700'}`}>
                <span className="font-medium">{msg.role === 'user' ? '你: ' : '顾问: '}</span>
                <span className="whitespace-pre-wrap line-clamp-2">{(msg.content || '').slice(0, 150)}</span>
              </div>
            ))}
            <Button onClick={() => setActiveTab('chat')} className="text-[10px] text-indigo-500 hover:underline mt-1">
              查看完整对话 →
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}
