import { useState, useEffect } from 'react';
import { Input } from '@/components/ui/input';

// ── UniGroup: collapsible university group ──
function UniGroup({ uniName, schools, trackedSchools, onTrack }) {
  const [expanded, setExpanded] = useState(true);

  const englishText = (s) => {
    if (!s.english_req) return s.english || '-';
    if (!s.english_req.required) return '不要求';
    return s.english_req.type || '必要';
  };

  return (
    <div className="border rounded-lg bg-white">
      <button onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 rounded-lg transition">
        <span className="text-sm font-semibold text-gray-800">{uniName}</span>
        <span className="flex items-center gap-2">
          <span className="text-xs text-gray-400">{schools.length} 个研究科</span>
          <span className="text-gray-400 text-xs">{expanded ? '▲' : '▼'}</span>
        </span>
      </button>
      {expanded && (
        <div className="px-4 pb-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          {schools.map((s, i) => {
            const alreadyTracked = trackedSchools.includes(s.name);
            return (
              <div key={i} className="border rounded-lg p-3 hover:shadow-sm transition">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-sm font-medium text-gray-800">{s.name}</h3>
                  <button onClick={() => onTrack(s)} disabled={alreadyTracked}
                    className={`text-xs px-2.5 py-1 rounded-lg transition font-medium shrink-0 ${
                      alreadyTracked ? 'bg-gray-100 text-gray-400 cursor-default' : 'bg-primary/10 hover:bg-indigo-100 text-primary'
                    }`}>
                    {alreadyTracked ? '已追踪' : '+ 追踪'}
                  </button>
                </div>
                {s.majors?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-1.5">
                    {s.majors.map(m => <span key={m} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">{m}</span>)}
                  </div>
                )}
                {s.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-1.5">
                    {s.tags.map(t => <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-500">{t}</span>)}
                  </div>
                )}
                {s.type && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium inline-block mb-1.5 ${
                    s.type === '国立' ? 'bg-blue-50 text-blue-600' :
                    s.type === '公立' ? 'bg-emerald-50 text-emerald-600' :
                    'bg-purple-50 text-purple-600'
                  }`}>{s.type}</span>
                )}
                <div className="text-[11px] text-gray-400">
                  JLPT: {s.jlpt_min || s.jlpt || '不要求'} | {'英语'}: {englishText(s)}
                  {s.exam ? ` | 考试: ${s.exam}` : ''}
                </div>
                {s.notes && <div className="text-[10px] text-gray-400 mt-1 italic line-clamp-2">{s.notes}</div>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Filter chip ──
function FilterChip({ active, color, children, ...props }) {
  const colorMap = {
    red: 'bg-red-50 border-red-300 text-red-600',
    green: 'bg-green-50 border-green-300 text-green-600',
    amber: 'bg-amber-50 border-amber-300 text-amber-600',
    indigo: 'bg-indigo-50 border-indigo-300 text-indigo-600',
    blue: 'bg-blue-50 border-blue-300 text-blue-600',
  };
  return (
    <button {...props} className={`text-[11px] px-2 py-1 rounded-full border transition ${
      active ? colorMap[color] || 'bg-indigo-50 border-indigo-300 text-indigo-600'
      : 'bg-gray-50 border-gray-200 text-gray-500'
    }`}>{children}</button>
  );
}

// ── PlazaView exported component ──
// Props: catalog, stage, token, apiCall, setStage, showToast, profile
export default function PlazaView({ catalog, stage, token, apiCall, setStage, showToast, profile, initialFilter }) {
  const [filter, setFilter] = useState(initialFilter || '');
  useEffect(() => { if (initialFilter) setFilter(initialFilter); }, [initialFilter]);
  const [eng, setEng] = useState(null);    // null=all, true=required, false=not
  const [jpn, setJpn] = useState(null);
  const [contact, setContact] = useState(false);
  const [exam, setExam] = useState([]);
  const [instType, setInstType] = useState([]);

  const trackedSchools = (stage?.applications || []).map(a => a.school);

  const handleTrack = async (s) => {
    try {
      await apiCall('/v1/applications', token, {
        method: 'POST',
        body: { school: s.name, major: s.majors?.[0] || '', official_deadlines: s.deadlines, notes: s.notes }
      });
      const updated = await apiCall('/v1/stage', token);
      setStage(updated);
      showToast(`已添加「${s.name}」`, 'success');
    } catch (err) {
      showToast(`添加失败: ${err.message}`);
    }
  };

  const hasFilters = filter || eng !== null || jpn !== null || contact || exam.length > 0 || instType.length > 0;

  const clearAll = () => {
    setFilter('');
    setEng(null); setJpn(null); setContact(false);
    setExam([]); setInstType([]);
  };

  // ── Filter logic ──
  let list = catalog;
  if (!filter) {
    list = list.filter(s => s.majors?.length > 0 || s.exam || s.notes || s.jlpt_min);
  } else {
    const q = filter.toLowerCase();
    list = list.filter(s => [s.name, ...(s.majors||[]), ...(s.tags||[]), s.notes||''].join(' ').toLowerCase().includes(q));
  }
  if (eng === true) list = list.filter(s => s.english_req?.required);
  if (eng === false) list = list.filter(s => !s.english_req?.required);
  if (jpn === true) list = list.filter(s => s.jlpt_min || s.jlpt);
  if (jpn === false) list = list.filter(s => !s.jlpt_min && !s.jlpt);
  if (contact) list = list.filter(s => (s.tags||[]).some(t => t.includes('内諾') || t.includes('連絡') || t.includes('事前')));
  if (exam.length) list = list.filter(s => exam.some(e => (s.tags||[]).includes(e) || (s.exam||'').includes(e)));
  if (instType.length) list = list.filter(s => instType.includes(s.type));

  // ── Group by university ──
  const groups = {};
  list.forEach(s => {
    const parts = (s.name || '').split(' ');
    const uni = parts.length > 1 ? parts[0] : '其他';
    if (!groups[uni]) groups[uni] = [];
    groups[uni].push(s);
  });
  const uniNames = Object.keys(groups).sort((a, b) => groups[b].length - groups[a].length);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-lg font-bold text-gray-800 mb-1">学校广场</h2>
        <p className="text-sm text-gray-400 mb-4">浏览学校信息，找到感兴趣的加入追踪</p>

        {/* Filter bar — all chips on one line */}
        <div className="flex items-center gap-1.5 flex-wrap mb-5">
          <Input value={filter} onChange={e => setFilter(e.target.value)}
            placeholder="搜索专业，如：情报理工..."
            className="w-44 p-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />

          <FilterChip active={eng !== null} color={eng === true ? 'red' : 'green'}
            onClick={() => setEng(eng === null ? true : eng === true ? false : null)}>
            {'英语'}{eng === true ? ':要' : eng === false ? ':不要' : ''}
          </FilterChip>
          <FilterChip active={jpn !== null} color={jpn === true ? 'red' : 'green'}
            onClick={() => setJpn(jpn === null ? true : jpn === true ? false : null)}>
            {'日语'}{jpn === true ? ':要' : jpn === false ? ':不要' : ''}
          </FilterChip>
          <FilterChip active={contact} color="amber" onClick={() => setContact(!contact)}>
            {'套磁'}{contact ? ':必须' : ''}
          </FilterChip>

          <span className="text-gray-200 mx-0.5">|</span>

          {['筆記', '面接', '書類選考'].map(t => (
            <FilterChip key={t} active={exam.includes(t)} color="indigo"
              onClick={() => setExam(exam.includes(t) ? exam.filter(x => x !== t) : [...exam, t])}>
              {t}
            </FilterChip>
          ))}

          <span className="text-gray-200 mx-0.5">|</span>

          {['国立', '公立', '私立'].map(t => (
            <FilterChip key={t} active={instType.includes(t)} color="blue"
              onClick={() => setInstType(instType.includes(t) ? instType.filter(x => x !== t) : [...instType, t])}>
              {t}
            </FilterChip>
          ))}

          {hasFilters && (
            <button onClick={clearAll} className="text-[11px] text-gray-400 hover:text-gray-600">{'清除'}</button>
          )}
        </div>

        {/* Results */}
        {list.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p className="text-lg mb-2">{'没有匹配的学校'}</p>
            <p className="text-sm">{'试试调整筛选条件'}</p>
          </div>
        ) : (
          <div className="space-y-3">
            <span className="text-xs text-gray-400">{list.length} 所研究科，{uniNames.length} 所大学</span>
            {uniNames.map(name => (
              <UniGroup key={name} uniName={name} schools={groups[name]}
                trackedSchools={trackedSchools} onTrack={handleTrack} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
