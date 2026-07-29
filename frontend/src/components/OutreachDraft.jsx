import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { apiCall } from '@/lib/api';
import { copyText } from '@/lib/utils';

function highlightPlaceholders(text) {
  if (!text) return '';
  // Placeholders are in 【id】 format (full-width brackets)
  return text.replace(
    /(【[^】]*】)/g,
    '<span class="bg-yellow-200 text-yellow-900 px-0.5 rounded" title="需自行填写">$1</span>'
  );
}

export default function OutreachDraft({ open, onClose, school, professorName, token }) {
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState(null);
  const [bodyJa, setBodyJa] = useState('');
  const [bodyZh, setBodyZh] = useState('');

  // Reset state when switching to a different professor
  useEffect(() => {
    setDraft(null);
    setError(null);
    setBodyJa('');
    setBodyZh('');
    setLoading(false);
  }, [school, professorName]);

  const [style, setStyle] = useState('formal_jp');

  // Generate draft on demand (not auto, user clicks button)
  const generateDraft = async () => {
    setLoading(true);
    setError(null);
    setDraft(null);
    try {
      const data = await apiCall('/v1/draft', token, {
        method: 'POST',
        body: { school_name: school, professor_name: professorName, style },
      });
      if (data.ok) {
        setDraft(data.draft);
        setBodyJa(data.draft.body || '');
      } else {
        setError(data.error || '生成失败');
      }
    } catch (err) {
      setError(err.message);
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            套磁邮件草稿 — {school} / {professorName}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Initial state: generate button */}
          {!draft && !loading && !error && (
            <div className="text-center py-8 space-y-3">
              <div className="flex items-center justify-center gap-2">
                <button onClick={() => setStyle('formal_jp')} className={`text-xs px-2 py-1 rounded ${style === 'formal_jp' ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-500'}`}>日文敬語</button>
                <button onClick={() => setStyle('formal_en')} className={`text-xs px-2 py-1 rounded ${style === 'formal_en' ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-500'}`}>English</button>
              </div>
              <Button onClick={generateDraft}
                className="bg-primary text-primary-foreground hover:bg-indigo-700 px-6">
                生成套磁邮件草稿
              </Button>
            </div>
          )}

          {/* Loading state */}
          {loading && (
            <div className="flex items-center justify-center py-8 gap-2 text-muted-foreground">
              <Loader2 size={18} className="animate-spin" />
              <span>正在生成草稿...</span>
            </div>
          )}

          {/* Error state */}
          {error && !loading && (
            <div className="bg-destructive/10 text-destructive p-3 rounded text-sm">
              {error}
              <Button onClick={generateDraft}
                className="ml-3 text-xs underline bg-transparent text-destructive hover:bg-transparent p-0 h-auto">
                重试
              </Button>
            </div>
          )}

          {/* Draft loaded */}
          {draft && (
            <>
              {/* Subject */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">邮件主题</label>
                <div className="bg-muted border border-border rounded p-2 text-sm">{draft.subject}</div>
              </div>

              {/* Japanese body */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">正文（日文）</label>
                <div className="mb-2 text-xs text-amber-600 flex items-center gap-2">
                  <span className="inline-block w-3 h-3 bg-yellow-200 rounded-sm border border-yellow-400"></span>
                  黄色部分为占位符，需自行填写教授相关内容
                </div>
                {/* Highlighted preview (read-only, visual reference) */}
                <div
                  className="w-full min-h-[120px] p-2 border border-border rounded text-sm leading-relaxed whitespace-pre-wrap overflow-auto mb-1 bg-card"
                  dangerouslySetInnerHTML={{ __html: highlightPlaceholders(bodyJa) }}
                />
                {/* Editable textarea */}
                <textarea
                  className="w-full min-h-[120px] p-2 border border-border rounded text-sm leading-relaxed bg-background"
                  value={bodyJa}
                  onChange={e => setBodyJa(e.target.value)}
                  placeholder="编辑正文..."
                />
                <div className="flex gap-2 mt-1">
                  <Button
                    onClick={() => copyText(bodyJa, '日文正文')}
                    className="text-xs px-3 py-1 rounded border bg-white text-muted-foreground hover:bg-muted"
                  >
                    复制正文（日文）
                  </Button>
                </div>
              </div>

              {/* Chinese translation */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">中文翻译（参考）</label>
                <div className="mb-2 text-xs text-amber-600 flex items-center gap-2">
                  <span className="inline-block w-3 h-3 bg-yellow-200 rounded-sm border border-yellow-400"></span>
                  黄色部分为占位符，需自行填写教授相关内容
                </div>
                {/* Highlighted preview */}
                <div
                  className="w-full min-h-[100px] p-2 border border-border rounded text-sm leading-relaxed whitespace-pre-wrap overflow-auto mb-1 bg-card"
                  dangerouslySetInnerHTML={{ __html: highlightPlaceholders(bodyZh) }}
                />
                {/* Editable textarea */}
                <textarea
                  className="w-full min-h-[100px] p-2 border border-border rounded text-sm leading-relaxed bg-background"
                  value={bodyZh}
                  onChange={e => setBodyZh(e.target.value)}
                  placeholder="编辑翻译..."
                />
                <div className="flex gap-2 mt-1">
                  <Button
                    onClick={() => copyText(bodyZh, '中文翻译')}
                    className="text-xs px-3 py-1 rounded border bg-white text-muted-foreground hover:bg-muted"
                  >
                    复制翻译（中文）
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
