import { useState, useEffect, useRef } from 'react';
import { Send, User, Bot, Loader2, LogOut, Settings, LayoutGrid, MessageCircle, Calendar } from 'lucide-react';

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
            if (parsed.suggested_schools) {
              suggested = parsed.suggested_schools;
              break;
            }
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

      // After streaming done, show school suggestions if any
      if (suggested.length > 0) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: '',
          suggestedSchools: suggested
        }]);
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
      <aside className="w-80 bg-white border-r flex flex-col shrink-0 overflow-hidden">
        <div className="p-5 border-b">
          <h1 className="text-lg font-bold text-gray-800">升学顾问</h1>
          <p className="text-xs text-gray-400 mt-0.5">{user?.email}</p>
        </div>

        <div className="flex-1 overflow-y-auto">
        {/* Stage + Applications */}
        {stage && (
          <div className="p-4 border-b">
            {/* Single progress bar — only show when no per-school cards */}
            {(!stage.applications || stage.applications.length === 0) && (
              <>
                <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">申请进度</h3>
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500 rounded-full transition-all"
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
                <button onClick={() => setShowAddSchool(!showAddSchool)}
                  className="text-xs px-2 py-0.5 rounded bg-indigo-50 hover:bg-indigo-100 text-indigo-600 transition font-medium"
                  title="添加学校">+ 添加</button>
              </div>

              {showAddSchool && (
                <form onSubmit={addSchool} className="border rounded-lg p-2.5 bg-indigo-50/50 space-y-1.5">
                  <input value={newSchool} onChange={e => setNewSchool(e.target.value)}
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
                    <button type="submit" disabled={!newSchool.trim()}
                      className="text-xs px-3 py-1.5 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-30 transition flex-1">添加</button>
                    <button type="button" onClick={() => setShowAddSchool(false)}
                      className="text-xs px-3 py-1.5 rounded bg-white text-gray-500 hover:bg-gray-100 transition border">取消</button>
                  </div>
                </form>
              )}

              {stage.applications?.map((app, i) => {
                  const stageColors = { browsing: 'bg-slate-100 text-slate-500', preparing: 'bg-gray-100 text-gray-600', contacting: 'bg-blue-100 text-blue-700',
                    applying: 'bg-purple-100 text-purple-700', exam: 'bg-orange-100 text-orange-700',
                    waiting: 'bg-amber-100 text-amber-700', decided: 'bg-green-100 text-green-700' };
                  const profStatusColors = { pending: 'text-gray-400', sent: 'text-blue-600',
                    replied: 'text-green-600', rejected: 'text-red-500', no_reply: 'text-amber-600',
                    interview: 'text-teal-600' };
                  const profStatusLabel = { pending: '待联系', sent: '已发信', replied: '已回复',
                    rejected: '婉拒', no_reply: '超期未回', interview: '获面试' };
                  return (
                    <div key={i} className="border rounded-lg p-2.5 bg-white hover:shadow-sm transition-shadow">
                      {/* Header: school + stage + delete */}
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-semibold text-gray-800 truncate max-w-[130px]" title={app.school}>
                          {app.school}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${stageColors[app.stage_id] || 'bg-gray-100 text-gray-600'}`}>
                            {app.label}
                          </span>
                          <button onClick={() => removeSchool(app.school)}
                            className="text-gray-300 hover:text-red-400 text-xs leading-none transition" title="删除">&times;</button>
                        </div>
                      </div>

                      {/* Progress mini-bar */}
                      <div className="h-1 bg-gray-100 rounded-full mb-1.5 overflow-hidden">
                        <div className="h-full bg-indigo-400 rounded-full transition-all"
                          style={{ width: `${(app.progress || 0) * 100}%` }}></div>
                      </div>

                      {/* Professors */}
                      {app.professors?.length > 0 && (
                        <div className="text-[10px] text-gray-500 mb-1">
                          {app.professors.map((p, j) => (
                            <span key={j} className={`mr-2 ${profStatusColors[p.status] || 'text-gray-400'}`}>
                              {p.name}({profStatusLabel[p.status] || p.status})
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Deadlines + Notes */}
                      {(app.deadlines && Object.keys(app.deadlines).length > 0) && (
                        <div className="text-[10px] text-gray-400 mb-1">
                          {Object.entries(app.deadlines).map(([k, v], j) => (
                            <span key={j} className="mr-2">{k}: {v}</span>
                          ))}
                        </div>
                      )}
                      {app.notes && (
                        <div className="text-[10px] text-gray-400 italic truncate mb-1">{app.notes}</div>
                      )}

                      {/* Stage buttons */}
                      {(app.next_stages?.length > 0 || app.prev_stages?.length > 0) && (
                        <div className="flex flex-wrap gap-1 mt-1.5 pt-1.5 border-t border-gray-50">
                          {app.prev_stages?.map(s => {
                            const key = 'back-' + s + app.school;
                            const label = s === 'contacting' ? '套磁' : s === 'applying' ? '出愿' : s === 'exam' ? '考试' : s === 'waiting' ? '等待' : s === 'decided' ? '确定' : s === 'preparing' ? '准备' : s;
                            return (
                              <button key={s} onClick={() => advanceStage(s, app.school)}
                                disabled={advancing === key}
                                className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 hover:bg-amber-100 text-amber-600 transition disabled:opacity-30">
                                {advancing === key ? '...' : `← ${label}`}
                              </button>
                            );
                          })}
                          {app.next_stages?.map(s => {
                            const key = s + app.school;
                            const label = s === 'contacting' ? '套磁' : s === 'applying' ? '出愿' : s === 'exam' ? '考试' : s === 'waiting' ? '等待' : s === 'decided' ? '确定' : s;
                            return (
                              <button key={s} onClick={() => advanceStage(s, app.school)}
                                disabled={advancing === key}
                                className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 hover:bg-indigo-100 text-gray-600 hover:text-indigo-700 transition disabled:opacity-30">
                                {advancing === key ? '...' : label}
                              </button>
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
                              <div key={j} className={`text-[10px] flex justify-between ${t.stage === app.stage_id ? 'font-medium text-indigo-600' : 'text-gray-400'}`}>
                                <span>{t.label}</span>
                                <span>{t.start} ~ {t.end}</span>
                              </div>
                            ))}
                          </div>
                        </details>
                      )}
                    </div>
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
                    <button key={'back-' + s} onClick={() => advanceStage(s)}
                      disabled={advancing === s}
                      className="text-xs px-2 py-1 rounded bg-amber-50 hover:bg-amber-100 text-amber-600 transition disabled:opacity-30 disabled:cursor-wait">
                      {advancing === s ? '处理中...' : `← 回退「${label}」`}
                    </button>
                  );
                })}
                {stage.next_stages?.map(s => {
                  const label = s === 'contacting' ? '套磁' : s === 'applying' ? '出愿' : s === 'exam' ? '考试' : s === 'waiting' ? '等待' : s === 'decided' ? '确定' : s;
                  return (
                    <button key={s} onClick={() => advanceStage(s)}
                      disabled={advancing === s}
                      className="text-xs px-2 py-1 rounded bg-gray-100 hover:bg-indigo-100 text-gray-600 hover:text-indigo-700 transition disabled:opacity-30 disabled:cursor-wait">
                      {advancing === s ? '处理中...' : `进入「${label}」`}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

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

        </div>{/* end scrollable area */}

        <div className="p-4 border-t shrink-0">
          <button onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-red-500 w-full p-2">
            <LogOut size={16} /> 退出
          </button>
        </div>
      </aside>

      {/* Main area: chat + plaza */}
      <main className="flex-1 flex flex-col">
        {/* Tab bar */}
        <div className="flex border-b bg-white px-4 shrink-0">
          <button onClick={() => setActiveTab('chat')}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition ${
              activeTab === 'chat' ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-gray-400 hover:text-gray-600'}`}>
            <MessageCircle size={16} /> 对话
          </button>
          <button onClick={() => { setActiveTab('plaza'); if (catalog.length === 0) apiCall('/v1/schools', token).then(r => setCatalog(r.schools)).catch(() => {}); }}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition ${
              activeTab === 'plaza' ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-gray-400 hover:text-gray-600'}`}>
            <LayoutGrid size={16} /> 广场
          </button>
          <button onClick={() => setActiveTab('calendar')}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition ${
              activeTab === 'calendar' ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-gray-400 hover:text-gray-600'}`}>
            <Calendar size={16} /> 日历
          </button>
        </div>

        {activeTab === 'chat' ? (
        <>
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-gray-700' : 'bg-indigo-600'}`}>
                {msg.role === 'user' ? <User size={14} className="text-white" /> : <Bot size={14} className="text-white" />}
              </div>
              <div className={`max-w-[75%] ${msg.role === 'user' ? 'bg-gray-800 text-white' : msg.suggestedSchools ? 'bg-indigo-50 border border-indigo-200' : 'bg-white border shadow-sm'} p-4 rounded-2xl text-sm leading-relaxed`}>
                {msg.content && <div className="whitespace-pre-wrap">{msg.content}</div>}
                {msg.suggestedSchools && (
                  <div>
                    <p className="text-gray-600 mb-2">要将这些学校加入申请追踪吗？</p>
                    <div className="flex flex-wrap gap-2">
                      {msg.suggestedSchools.map(school => (
                        <button key={school} onClick={async () => {
                          try {
                            await apiCall('/v1/applications', token, { method: 'POST', body: { school } });
                            const updated = await apiCall('/v1/stage', token);
                            setStage(updated);
                            setMessages(prev => prev.map(m => m.suggestedSchools ? { ...m, suggestedSchools: null, content: `已添加「${school}」到追踪列表` } : m));
                          } catch (err) { showToast(`添加失败: ${err.message}`); }
                        }}
                          className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition font-medium">
                          + {school}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex items-center gap-2 text-gray-400 text-sm ml-11">
              <Loader2 size={14} className="animate-spin" /> 思考中...
            </div>
          )}
        </div>
        <div className="p-4 border-t bg-white">
          <div className="max-w-3xl mx-auto flex gap-3">
            <input value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendMessage()} disabled={loading}
              placeholder="输入你的留学疑问..."
              className="flex-1 p-3 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            <button onClick={sendMessage} disabled={loading || !input.trim()}
              className="w-12 h-12 flex items-center justify-center bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition shrink-0">
              <Send size={18} />
            </button>
          </div>
        </div>
        </>
        ) : activeTab === 'plaza' ? (
        /* Plaza view */
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-5xl mx-auto">
            <h2 className="text-lg font-bold text-gray-800 mb-1">学校广场</h2>
            <p className="text-sm text-gray-400 mb-4">浏览学校信息，找到感兴趣的加入追踪</p>
            <input value={plazaFilter} onChange={e => setPlazaFilter(e.target.value)}
              placeholder="筛选专业，如：情报理工、NLP..."
              className="w-full max-w-md p-2.5 border rounded-lg text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {catalog.filter(s => !plazaFilter || s.majors?.some(m => m.includes(plazaFilter)) || s.name.includes(plazaFilter)).map((s, i) => (
                <div key={i} className="border rounded-xl p-4 bg-white hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-sm font-semibold text-gray-800">{s.name}</h3>
                    <button onClick={async () => {
                      try {
                        await apiCall('/v1/applications', token, { method: 'POST', body: { school: s.name, deadlines: s.deadlines, notes: s.notes } });
                        const updated = await apiCall('/v1/stage', token);
                        setStage(updated);
                        showToast(`已添加「${s.name}」`, 'success');
                      } catch (err) { showToast(`添加失败: ${err.message}`); }
                    }}
                      className="text-xs px-2.5 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-600 transition font-medium shrink-0">
                      追踪
                    </button>
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
                </div>
              ))}
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
                          <div key={mi} className={`flex-1 min-w-[55px] border-l ${isCurrent ? 'bg-indigo-50/40' : ''}`}>
                            <div className={`h-8 text-center text-[10px] pt-2 font-medium ${isCurrent ? 'text-indigo-600' : 'text-gray-400'}`}>
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
                    <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-indigo-50 inline-block"></span> 本月</span>
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
        )}
      </main>
    </div>
  );
}
