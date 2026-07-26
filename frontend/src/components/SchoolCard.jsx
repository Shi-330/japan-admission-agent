import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

/**
 * Reusable school card for plaza and chat.
 *
 * Props:
 *   school: {name, type, majors, tags, jlpt_min, jlpt, english_req, english, exam, deadlines, notes}
 *   status: optional match result — {status_label, gaps: [{field, required, current, met}]}
 *   alreadyTracked: bool
 *   onTrack: async callback
 *   compact: bool — thinner layout for inline chat rendering
 */
export default function SchoolCard({ school: s, status, alreadyTracked, onTrack, compact }) {
  const typeBadge = s.type && (
    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
      s.type === '国立' ? 'bg-blue-50 text-blue-600' :
      s.type === '公立' ? 'bg-emerald-50 text-emerald-600' :
      'bg-purple-50 text-purple-600'
    }`}>{s.type}</span>
  );

  const englishText = s.english_req
    ? (s.english_req.required ? (s.english_req.type + (s.english_req.min_score ? ' ' + s.english_req.min_score : '')) : '-')
    : (s.english || '-');

  if (compact) {
    return (
      <div className="border rounded-lg p-3 bg-card">
        <div className="flex items-center justify-between mb-1">
          <h4 className="text-sm font-semibold truncate flex-1">
            {s.name} {typeBadge}
          </h4>
          {onTrack && !alreadyTracked && (
            <Button onClick={onTrack} size="sm" className="text-xs px-2 py-1 h-auto ml-2 shrink-0">
              + 追踪
            </Button>
          )}
          {alreadyTracked && (
            <span className="text-xs text-muted-foreground ml-2 shrink-0">已追踪</span>
          )}
        </div>
        {status && (
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
              status.status_label === '可报考' ? 'bg-stage-contacting/15 text-stage-contacting' :
              status.status_label === '条件不足' ? 'bg-urgency-medium/15 text-urgency-medium' :
              'bg-urgency-high/15 text-urgency-high'
            }`}>{status.status_label}</span>
            <span className="text-xs text-muted-foreground">
              JLPT {s.jlpt_min || '-'} | {englishText} | {s.exam || '-'}
            </span>
          </div>
        )}
        {status?.gaps?.some(g => !g.met) && (
          <div className="flex flex-wrap gap-1 mt-1">
            {status.gaps.filter(g => !g.met).map((g, i) => (
              <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-urgency-high/10 text-urgency-high">
                {g.field}: {g.current} vs {g.required}
              </span>
            ))}
          </div>
        )}
        {!status && (
          <div className="text-xs text-muted-foreground">
            JLPT: {s.jlpt_min || s.jlpt || '-'} | 英语: {englishText} | 考试: {s.exam || '-'}
          </div>
        )}
      </div>
    );
  }

  // Full card (plaza)
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between mb-2">
          <h3 className="text-sm font-semibold text-gray-800">
            {s.name} {typeBadge}
          </h3>
          {onTrack && (
            <Button
              onClick={onTrack}
              disabled={alreadyTracked}
              className={`text-xs px-2.5 py-1 rounded-lg transition font-medium shrink-0 ${
                alreadyTracked ? 'bg-gray-100 text-gray-400' : 'bg-primary/10 hover:bg-indigo-100 text-primary'
              }`}
            >
              {alreadyTracked ? '已追踪' : '追踪'}
            </Button>
          )}
        </div>

        {s.majors?.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {s.majors.map(m => (
              <span key={m} className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">{m}</span>
            ))}
          </div>
        )}

        {s.tags?.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {s.tags.map(t => (
              <span key={t} className="text-xs px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-500">{t}</span>
            ))}
          </div>
        )}

        <div className="text-xs text-gray-400 space-y-0.5 mb-2">
          <div>JLPT: {s.jlpt_min || s.jlpt || '不要求'} | 英语: {englishText} | 考试: {s.exam || '-'}</div>
        </div>

        {status && (
          <div className="mb-2">
            <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
              status.status_label === '可报考' ? 'bg-stage-contacting/15 text-stage-contacting' :
              status.status_label === '条件不足' ? 'bg-urgency-medium/15 text-urgency-medium' :
              'bg-urgency-high/15 text-urgency-high'
            }`}>
              {status.status_label}
            </span>
            {status.gaps?.some(g => !g.met) && (
              <div className="flex flex-wrap gap-1 mt-1">
                {status.gaps.filter(g => !g.met).map((g, i) => (
                  <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-urgency-high/10 text-urgency-high">
                    {g.field}: 需要{g.required}，当前{g.current}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

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
      </CardContent>
    </Card>
  );
}
