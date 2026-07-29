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
// Clean raw enrichment notes: strip URLs, extract structured tags, remove cross-school contamination
function cleanNotes(raw, schoolName) {
  if (!raw) return { text: '', tags: [] };
  let text = raw;
  // Strip URLs
  text = text.replace(/https?:\/\/[^\s）)】。]+/g, '');
  // Strip cross-school contamination: sentences mentioning other universities not in this school's name
  if (schoolName) {
    const ownUni = schoolName.split(' ')[0]; // e.g. "関西大学" from "関西大学 情報科学研究科"
    const knownUnis = ['東京大学', '京都大学', '大阪大学', '東北大学', '九州大学', '北海道大学', '名古屋大学', '早稲田大学', '慶應義塾大学', '筑波大学', '東京工業大学', '東京科学大学', '一橋大学', '横浜国立大学', '神戸大学', '広島大学'];
    for (const uni of knownUnis) {
      if (uni !== ownUni && text.includes(uni)) {
        // Remove sentences containing other university names
        text = text.replace(new RegExp(`[^。.]*${uni}[^。.]*[。.]?`, 'g'), '');
      }
    }
  }
  // Extract 【keyword】content  patterns as tags
  const tags = [];
  text = text.replace(/【(.+?)】\s*([^【]*?)(?=\s*【|$)/g, (_, key, val) => {
    const cleanVal = val.trim().replace(/[|｜]\s*$/, '');
    if (cleanVal && cleanVal.length < 40) {
      tags.push({ key, val: cleanVal });
    }
    return '';
  });
  // Clean up
  text = text.replace(/^[|｜\s]+/, '').replace(/[|｜\s]+$/, '').replace(/\s{2,}/g, ' ').trim();
  return { text, tags };
}

// Compute match score 0-100 based on JLPT + English + GPA requirements
function computeScore(school, profile) {
  if (!profile) return null;
  let total = 0, met = 0;
  const jlpt = school.jlpt_min || school.jlpt;
  if (jlpt) { total++; const userJ = profile.jlpt_level || 'N5'; const order = ['N5','N4','N3','N2','N1']; if (order.indexOf(userJ) >= order.indexOf(jlpt)) met++; }
  if (school.english_req?.required) { total++; if (profile.english_score && profile.english_score !== '无') met++; }
  if (school.gpa_min > 0 && profile.gpa) { total++; if (parseFloat(profile.gpa) >= school.gpa_min) met++; }
  if (total === 0) return null;
  const score = Math.round((met / total) * 100);
  return { score, met, total };
}

export default function SchoolCard({ school: s, status, alreadyTracked, onTrack, compact, profile }) {
  const { text: cleanNote, tags: noteTags } = cleanNotes(s.notes, s.name);
  const matchScore = computeScore(s, profile);
  const scoreColor = !matchScore ? '' : matchScore.score >= 80 ? 'text-green-600' : matchScore.score >= 50 ? 'text-amber-600' : 'text-red-600';
  const scoreLabel = !matchScore ? '' : matchScore.score >= 80 ? '稳妥' : matchScore.score >= 50 ? '冲刺' : '差距较大';
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
            {matchScore && <span className={`ml-1 text-[10px] font-normal ${scoreColor}`}>{scoreLabel} {matchScore.score}%</span>}
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
              status.status_label === '参考' ? 'bg-muted text-muted-foreground' :
              'bg-urgency-high/15 text-urgency-high'
            }`}>{status.status_label}</span>
            {(s.jlpt_min || englishText !== '-' || s.exam) && (
              <span className="text-xs text-muted-foreground">
                {s.jlpt_min ? `JLPT ${s.jlpt_min}` : ''}
                {s.jlpt_min && englishText !== '-' ? ' | ' : ''}
                {englishText !== '-' ? englishText : ''}
                {((s.jlpt_min || englishText !== '-') && s.exam) ? ' | ' : ''}
                {s.exam || ''}
              </span>
            )}
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
        {!status && (s.jlpt_min || englishText !== '-' || s.exam) && (
          <div className="text-xs text-muted-foreground">
            JLPT: {s.jlpt_min || s.jlpt || '-'} | 英语: {englishText} | 考试: {s.exam || '-'}
          </div>
        )}
        {noteTags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {noteTags.map((t, i) => <span key={i} className="text-[9px] px-1 py-0.5 rounded bg-amber-50 text-amber-700">{t.key}: {t.val}</span>)}
          </div>
        )}
        {cleanNote && (
          <div className="text-[10px] text-muted-foreground mt-1">{cleanNote}</div>
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

        {noteTags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {noteTags.map((t, i) => <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700">{t.key}: {t.val}</span>)}
          </div>
        )}
        {cleanNote && <div className="text-xs text-gray-400 mt-1">{cleanNote}</div>}
      </CardContent>
    </Card>
  );
}
