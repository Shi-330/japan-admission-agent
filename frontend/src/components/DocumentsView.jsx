import { useState, useEffect, useCallback } from 'react';
import { Loader2, FileText, Trash2, Copy, RefreshCw, ChevronDown, ChevronRight, Plus, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { apiCall } from '@/lib/api';
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
      </div>
    </div>
  );
}
