import { useState, useEffect, useCallback, useRef } from 'react';
import { Loader2, FileText, Trash2, Copy, RefreshCw, ChevronDown, ChevronRight, Plus, X, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { apiCall, apiUpload } from '@/lib/api';
import { copyText } from '@/lib/utils';

// ── Sub-components ──

/** Reusable label + copy button + scrollable text block for ja/zh body sections */
function DraftBodySection({ label, copyLabel, content }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs font-medium text-muted-foreground">{label}</label>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => copyText(content, copyLabel)}
          className="text-xs h-6 px-2 text-muted-foreground hover:text-foreground"
        >
          <Copy size={10} className="mr-1" /> 复制
        </Button>
      </div>
      <div className="text-sm leading-relaxed whitespace-pre-wrap bg-card border border-border rounded p-2.5 max-h-60 overflow-y-auto">
        {content || '(无内容)'}
      </div>
    </div>
  );
}

// ── Helpers ──

function formatDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const INITIAL_FORM = { show: false, school: '', prof: '', suggestions: [] };

export default function DocumentsView({ token, onRegenerate, applications }) {
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [deleting, setDeleting] = useState(new Set());
  const [form, setForm] = useState(INITIAL_FORM);

  const resetForm = () => setForm(INITIAL_FORM);

  // ── 材料清单(todo)──
  const [checklists, setChecklists] = useState([]);
  const [checklistLoading, setChecklistLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadSchool, setUploadSchool] = useState('');
  const fileInputRef = useRef(null);
  const [newItemNames, setNewItemNames] = useState({}); // { checklistId: 输入中的新条目名 }

  const fetchChecklists = useCallback(async () => {
    if (!token) return;
    setChecklistLoading(true);
    try {
      const data = await apiCall('/v1/checklists', token);
      setChecklists(data.checklists || []);
    } catch (err) {
      /* ignore */
    } finally {
      setChecklistLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchChecklists();
  }, [fetchChecklists]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await apiUpload('/v1/documents/extract', token, file, { school: uploadSchool });
      toast.success('已生成材料清单');
      setUploadSchool('');
      if (fileInputRef.current) fileInputRef.current.value = '';
      fetchChecklists();
    } catch (err) {
      toast.error(err.message || '上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleToggle = async (checklistId, itemIndex) => {
    try {
      await apiCall('/v1/checklists/toggle', token, { method: 'POST', body: { checklist_id: checklistId, item_index: itemIndex } });
      fetchChecklists();
    } catch (err) {
      toast.error('操作失败');
    }
  };

  const handleCreateChecklist = async () => {
    try {
      await apiCall('/v1/checklists', token, { method: 'POST', body: { school: uploadSchool } });
      toast.success('已新建清单');
      setUploadSchool('');
      fetchChecklists();
    } catch (err) {
      toast.error(err.message || '新建失败');
    }
  };

  const handleDeleteChecklist = async (checklistId) => {
    try {
      await apiCall('/v1/checklists', token, { method: 'DELETE', body: { checklist_id: checklistId } });
      fetchChecklists();
    } catch (err) {
      toast.error('删除失败');
    }
  };

  const handleAddItem = async (checklistId) => {
    const name = (newItemNames[checklistId] || '').trim();
    if (!name) return;
    try {
      await apiCall('/v1/checklists/items', token, { method: 'POST', body: { checklist_id: checklistId, name } });
      setNewItemNames(prev => ({ ...prev, [checklistId]: '' }));
      fetchChecklists();
    } catch (err) {
      toast.error('添加失败');
    }
  };

  const handleDeleteItem = async (checklistId, itemIndex) => {
    try {
      await apiCall('/v1/checklists/items', token, { method: 'DELETE', body: { checklist_id: checklistId, item_index: itemIndex } });
      fetchChecklists();
    } catch (err) {
      toast.error('删除失败');
    }
  };

  const fetchDrafts = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall('/v1/drafts', token);
      setDrafts(data.drafts || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchDrafts();
  }, [fetchDrafts]);

  const handleDelete = async (draftId) => {
    setDeleting(prev => new Set(prev).add(draftId));
    try {
      await apiCall('/v1/drafts', token, { method: 'DELETE', body: { draft_id: draftId } });
      setDrafts(prev => prev.filter(d => d.id !== draftId));
      if (expandedId === draftId) setExpandedId(null);
      toast.success('已删除');
    } catch (err) {
      toast.error('删除失败，请重试');
    } finally {
      setDeleting(prev => {
        const next = new Set(prev);
        next.delete(draftId);
        return next;
      });
    }
  };

  const handleNewDraft = () => {
    const s = form.school.trim();
    const p = form.prof.trim();
    if (!s || !p) return;
    onRegenerate?.({ school: s, professorName: p });
    resetForm();
  };

  const handleSchoolInput = (value) => {
    setForm(prev => ({ ...prev, school: value }));
    if (value && (applications || []).length > 0) {
      const suggestions = applications.filter(a =>
        a.school.toLowerCase().includes(value.toLowerCase())
      ).slice(0, 5);
      setForm(prev => ({ ...prev, suggestions }));
    } else {
      setForm(prev => ({ ...prev, suggestions: [] }));
    }
  };

  const selectSchool = (school) => {
    setForm(prev => ({
      ...prev,
      school: school.school,
      suggestions: [],
      prof: school.professors?.length === 1 ? school.professors[0].name : prev.prof,
    }));
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-gray-800 mb-0.5">文书</h2>
            <p className="text-sm text-gray-400">套磁信草稿存档，可查看、复制、重新生成</p>
          </div>
          <Button
            onClick={() => setForm(prev => ({ ...prev, show: !prev.show }))}
            className="text-xs px-3 py-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-indigo-700"
          >
            <Plus size={14} className="mr-1" />
            新建套磁信
          </Button>
        </div>

        {/* New draft form */}
        {form.show && (
          <div className="border border-indigo-200 rounded-lg bg-indigo-50/50 p-4 mb-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-indigo-800">生成新套磁信</span>
              <button onClick={resetForm} className="text-gray-400 hover:text-gray-600">
                <X size={14} />
              </button>
            </div>
            <div className="space-y-3">
              <div className="relative">
                <label className="block text-xs text-gray-500 mb-1">学校</label>
                <Input
                  value={form.school}
                  onChange={e => handleSchoolInput(e.target.value)}
                  placeholder="如：京都大学 情报理工"
                  className="w-full text-sm p-2 border rounded"
                  autoFocus
                />
                {form.suggestions.length > 0 && (
                  <div className="absolute z-10 top-full mt-0.5 w-full bg-white border border-border rounded shadow-lg max-h-40 overflow-y-auto">
                    {form.suggestions.map((s, i) => (
                      <button
                        key={i}
                        onClick={() => selectSchool(s)}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-indigo-50 border-b border-gray-50 last:border-0"
                      >
                        <span className="font-medium">{s.school}</span>
                        {s.professors?.length > 0 && (
                          <span className="text-xs text-muted-foreground ml-2">
                            ({s.professors.map(p => p.name).join('、')})
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">教授姓名</label>
                <Input
                  value={form.prof}
                  onChange={e => setForm(prev => ({ ...prev, prof: e.target.value }))}
                  placeholder="如：田中太郎"
                  className="w-full text-sm p-2 border rounded"
                  onKeyDown={e => { if (e.key === 'Enter') handleNewDraft(); }}
                />
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={handleNewDraft}
                  disabled={!form.school.trim() || !form.prof.trim()}
                  className="text-xs px-4 py-1.5 rounded bg-primary text-primary-foreground hover:bg-indigo-700 disabled:opacity-30"
                >
                  生成草稿
                </Button>
                <Button onClick={resetForm} variant="outline" className="text-xs px-4 py-1.5 rounded">
                  取消
                </Button>
              </div>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center h-32">
            <Loader2 size={20} className="animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
            <p className="text-sm mb-2">加载失败</p>
            <Button variant="outline" size="sm" onClick={fetchDrafts} className="text-xs">
              <RefreshCw size={12} className="mr-1" /> 重试
            </Button>
          </div>
        ) : drafts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
            <FileText size={32} className="mb-3 text-gray-300" />
            <p className="text-sm">暂无存档草稿</p>
            <p className="text-xs mt-1">通过提醒或志愿校卡片的"拟套磁信"生成的草稿会自动存到这里</p>
          </div>
        ) : (
          <div className="space-y-2">
            {drafts.map((draft) => {
              const isExpanded = expandedId === draft.id;
              const isDeleting = deleting.has(draft.id);
              return (
                <div
                  key={draft.id}
                  className="border border-border rounded-lg bg-card overflow-hidden"
                >
                  {/* Header row */}
                  <div className="flex items-center justify-between p-3">
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : draft.id)}
                      className="flex items-center gap-2 flex-1 min-w-0 text-left hover:text-foreground transition-colors"
                    >
                      {isExpanded ? <ChevronDown size={14} className="shrink-0 text-muted-foreground" /> : <ChevronRight size={14} className="shrink-0 text-muted-foreground" />}
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-foreground truncate">{draft.subject || '(无主题)'}</p>
                        <p className="text-xs text-muted-foreground">
                          {draft.school} / {draft.professor_name}
                          <span className="mx-1.5">·</span>
                          {formatDate(draft.created_at)}
                        </p>
                      </div>
                    </button>
                    <div className="flex items-center gap-1 shrink-0 ml-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onRegenerate?.({ school: draft.school, professorName: draft.professor_name })}
                        className="text-xs text-muted-foreground hover:text-indigo-500 h-7 px-2"
                        title="重新生成"
                      >
                        <RefreshCw size={12} className="mr-1" />
                        重生成
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(draft.id)}
                        disabled={isDeleting}
                        className="text-xs text-muted-foreground hover:text-red-500 h-7 px-2"
                        title="删除"
                      >
                        {isDeleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                      </Button>
                    </div>
                  </div>

                  {/* Expanded content */}
                  {isExpanded && (
                    <div className="border-t border-border p-3 space-y-3 bg-muted/30">
                      <DraftBodySection label="正文（日文）" copyLabel="日文正文" content={draft.body_ja} />
                      <DraftBodySection label="中文翻译（参考）" copyLabel="中文翻译" content={draft.body_zh} />

                      {/* Placeholders */}
                      {draft.placeholders && draft.placeholders.length > 0 && (
                        <div>
                          <label className="text-xs font-medium text-muted-foreground mb-1 block">占位符提示</label>
                          <div className="flex flex-wrap gap-1.5">
                            {draft.placeholders.map((ph, i) => (
                              <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                                [{ph.id}] {ph.hint_ja || ph.hint_zh}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ── 材料清单 ── */}
        <div className="mt-8">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-base font-bold text-gray-800">材料清单</h3>
              <p className="text-xs text-gray-400">上传募集要项(PDF/Excel),自动提炼需提交的材料</p>
            </div>
            <div className="flex items-center gap-2">
              <Input
                value={uploadSchool}
                onChange={e => setUploadSchool(e.target.value)}
                placeholder="学校名(可选)"
                className="w-44 text-xs p-1.5 border rounded"
              />
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.xlsx,.xls"
                className="hidden"
                onChange={handleUpload}
              />
              <Button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="text-xs px-3 py-1.5 rounded bg-primary text-primary-foreground hover:bg-indigo-700 disabled:opacity-40"
              >
                {uploading ? <Loader2 size={12} className="animate-spin mr-1" /> : <Upload size={12} className="mr-1" />}
                上传募集要项
              </Button>
              <Button
                onClick={handleCreateChecklist}
                variant="outline"
                className="text-xs px-3 py-1.5 rounded"
              >
                <Plus size={12} className="mr-1" />
                新建空清单
              </Button>
            </div>
          </div>

          {checklistLoading ? (
            <div className="text-center text-muted-foreground text-sm py-6"><Loader2 size={16} className="animate-spin inline" /></div>
          ) : checklists.length === 0 ? (
            <div className="text-center text-muted-foreground text-sm py-6">暂无材料清单,上传募集要项或新建空清单</div>
          ) : (
            <div className="space-y-3">
              {checklists.map((cl) => {
                const items = cl.items || [];
                const doneCount = items.filter(i => i.done).length;
                return (
                  <div key={cl.id} className="border border-border rounded-lg bg-card overflow-hidden">
                    <div className="flex items-center justify-between px-3 py-2 bg-muted/40 border-b border-border">
                      <span className="text-sm font-medium text-foreground">{cl.school || '通用材料'}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">{doneCount}/{items.length}</span>
                        <button onClick={() => handleDeleteChecklist(cl.id)} className="text-muted-foreground hover:text-red-500" title="删除清单">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                    <div className="p-3 space-y-1.5">
                      {items.map((item, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-sm group">
                          <input
                            type="checkbox"
                            checked={!!item.done}
                            onChange={() => handleToggle(cl.id, idx)}
                            className="w-4 h-4 accent-indigo-600 shrink-0"
                          />
                          <span className={item.done ? 'line-through text-muted-foreground flex-1' : 'text-foreground flex-1'}>{item.name}</span>
                          <button
                            onClick={() => handleDeleteItem(cl.id, idx)}
                            className="text-muted-foreground hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                            title="删除"
                          >
                            <X size={12} />
                          </button>
                        </div>
                      ))}
                      <div className="flex items-center gap-2 pt-2 mt-1 border-t border-border">
                        <Input
                          value={newItemNames[cl.id] || ''}
                          onChange={e => setNewItemNames(prev => ({ ...prev, [cl.id]: e.target.value }))}
                          onKeyDown={e => { if (e.key === 'Enter') handleAddItem(cl.id); }}
                          placeholder="添加材料…"
                          className="flex-1 text-xs p-1.5 border rounded"
                        />
                        <Button
                          onClick={() => handleAddItem(cl.id)}
                          className="text-xs px-3 py-1.5 rounded bg-primary text-primary-foreground hover:bg-indigo-700"
                        >
                          添加
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
