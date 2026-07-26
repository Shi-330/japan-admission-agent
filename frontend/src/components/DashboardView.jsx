import { Loader2, ChevronRight, Bell, Calendar, School, User, ArrowRight, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import EmptyState from '@/components/EmptyState';

/** Map stage id to Tailwind color classes (bg + text) using stage-* tokens. */
const STAGE_PILL = {
  preparing: 'bg-stage-preparing/12 text-stage-preparing',
  contacting: 'bg-stage-contacting/12 text-stage-contacting',
  applying: 'bg-stage-applying/12 text-stage-applying',
  exam: 'bg-stage-exam/12 text-stage-exam',
  waiting: 'bg-stage-waiting/12 text-stage-waiting',
  decided: 'bg-stage-decided/12 text-stage-decided',
};

const STAGE_LABEL = { preparing: '准备', contacting: '套磁', applying: '出愿', exam: '考试', waiting: '等待', decided: '确定' };

const STAGE_ORDER = ['preparing', 'contacting', 'applying', 'exam', 'waiting', 'decided'];

/**
 * Urgency color for deadline countdown: bg + text + optional pulse.
 * Returns { bg, text, pulse } classes.
 */
function urgencyClasses(days) {
  if (days < 0) return { bg: 'bg-urgency-high/10', text: 'text-urgency-high', pulse: false };
  if (days <= 7) return { bg: 'bg-urgency-high/10', text: 'text-urgency-high', pulse: true };
  if (days <= 14) return { bg: 'bg-urgency-medium/10', text: 'text-urgency-medium', pulse: false };
  return { bg: 'bg-card', text: 'text-muted-foreground', pulse: false };
}

/**
 * A small SVG ring showing X/Y completeness.
 */
function ProfileRing({ filled, total, percentage, onClick }) {
  const r = 32;
  const circ = 2 * Math.PI * r;
  const offset = circ - (percentage / 100) * circ;
  return (
    <button
      onClick={onClick}
      className="relative flex-shrink-0 group"
      title="编辑画像"
    >
      <svg width="80" height="80" className="-rotate-90">
        <circle cx="40" cy="40" r={r} fill="none" stroke="currentColor"
          strokeWidth="5" className="text-muted/30" />
        <circle cx="40" cy="40" r={r} fill="none" stroke="currentColor"
          strokeWidth="5" strokeLinecap="round"
          className="text-brand transition-all duration-700"
          strokeDasharray={circ} strokeDashoffset={offset} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-bold tabular-nums leading-tight">{percentage}%</span>
        <span className="text-[10px] text-muted-foreground">{filled}/{total}项</span>
      </div>
    </button>
  );
}

export default function DashboardView({ greeting, applications, profile, loading, onNavigate, onEditProfile }) {
  // ---- Loading ----
  if (loading || !greeting) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">加载中...</span>
      </div>
    );
  }

  const { message, has_reminders, profile_completeness, next_actions, when: whenArr, structural_risk, gates } = greeting;
  const counts = greeting.counts || { total_apps: 0, overdue_profs: 0, upcoming_deadlines: 0 };
  const pc = profile_completeness || { filled: 0, total: 6, percentage: 0 };

  // ---- Empty profile (no data at all) ----
  if (pc.filled === 0 && (!applications || applications.length === 0)) {
    return (
      <EmptyState
        icon={User}
        title="填写背景信息，开启个性化推荐"
        description="完善日语能力、英语成绩、GPA、本科院校等信息，获取精准的学校匹配和申请建议"
        action={{ label: '去填写', onClick: onEditProfile }}
      />
    );
  }

  // ---- Group schools by stage ----
  const grouped = {};
  for (const s of STAGE_ORDER) {
    const apps = (applications || []).filter(a => (a.stage_id || a.stage) === s);
    if (apps.length > 0) grouped[s] = apps;
  }

  // ---- Nearest deadline ----
  let nearestDl = null;
  for (const app of (applications || [])) {
    for (const [name, dateStr] of Object.entries(app.deadlines || {})) {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) continue;
      const days = Math.ceil((d - new Date()) / 86400000);
      if (nearestDl === null || (days >= 0 && days < nearestDl.days)) {
        nearestDl = { school: app.school, name, days, date: dateStr };
      }
    }
  }

  const totalAlerts = counts.overdue_profs + counts.upcoming_deadlines;

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto space-y-5">

        {/* ====== Hero Row: Greeting + Profile Ring ====== */}
        <div className="flex items-start gap-5">
          <div className={`flex-1 p-4 rounded-xl ${has_reminders ? 'bg-urgency-medium/10 border border-urgency-medium/30' : 'bg-card border'}`}>
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{message}</p>
          </div>
          {pc.total > 0 && (
            <ProfileRing filled={pc.filled} total={pc.total} percentage={pc.percentage} onClick={onEditProfile} />
          )}
        </div>

        {/* ====== KPI Cards ====== */}
        <div className="grid grid-cols-3 gap-3">
          {/* Schools */}
          <Card className="group cursor-pointer hover:shadow-md transition-shadow" onClick={() => onNavigate('plaza')}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <School size={14} className="text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground">志愿校</span>
              </div>
              <div className="text-2xl font-bold tabular-nums">{counts.total_apps}</div>
              <div className="text-xs text-muted-foreground mt-0.5 group-hover:text-brand transition-colors">
                去广场 <ArrowRight size={10} className="inline ml-0.5" />
              </div>
            </CardContent>
          </Card>

          {/* Deadlines */}
          <Card className={nearestDl && nearestDl.days <= 7 ? 'bg-urgency-high/10 border-urgency-high/40' : ''}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Calendar size={14} className={nearestDl && nearestDl.days <= 7 ? 'text-urgency-high' : 'text-muted-foreground'} />
                <span className="text-xs font-medium text-muted-foreground">截止日</span>
              </div>
              <div className={`text-2xl font-bold tabular-nums ${nearestDl && nearestDl.days <= 7 ? 'text-urgency-high' : ''}`}>
                {counts.upcoming_deadlines}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {nearestDl ? `最近: ${nearestDl.days}天后` : '暂无临近截止日'}
              </div>
            </CardContent>
          </Card>

          {/* Alerts */}
          <Card className={totalAlerts > 0 ? 'bg-urgency-medium/10 border-urgency-medium/40' : ''}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Bell size={14} className={totalAlerts > 0 ? 'text-urgency-medium' : 'text-muted-foreground'} />
                <span className="text-xs font-medium text-muted-foreground">需关注</span>
              </div>
              <div className={`text-2xl font-bold tabular-nums ${totalAlerts > 0 ? 'text-urgency-medium' : ''}`}>
                {totalAlerts}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {totalAlerts > 0
                  ? [counts.overdue_profs > 0 && `${counts.overdue_profs}教授超期`, counts.upcoming_deadlines > 0 && `${counts.upcoming_deadlines}截止日`].filter(Boolean).join(' / ')
                  : '一切顺利'}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ====== Application Rhythm (whenArr) ====== */}
        {whenArr && whenArr.length > 0 && (
          <div className="border rounded-xl overflow-hidden">
            <div className="bg-card px-4 py-2.5 border-b flex items-center gap-2">
              <Clock size={14} className="text-muted-foreground" />
              <span className="text-sm font-semibold">申请节奏</span>
              <span className="text-xs text-muted-foreground">本周行动指南</span>
            </div>
            <div className="divide-y">
              {whenArr.map((item, i) => {
                const pill = STAGE_PILL[item.stage] || 'bg-muted text-muted-foreground';
                return (
                  <div key={i} className="px-4 py-3 flex items-center justify-between hover:bg-muted/30 transition-colors group">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-sm font-medium truncate max-w-[160px]">{item.school}</span>
                      {item.major && <span className="text-xs text-muted-foreground hidden sm:inline shrink-0">{item.major}</span>}
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${pill}`}>
                        {item.verdict}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground text-right shrink-0 ml-4 max-w-[200px] truncate hidden sm:inline">
                      {item.reason}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ====== Structural Risk ====== */}
        {structural_risk && (
          <div className="p-3 rounded-lg border bg-urgency-medium/10 border-urgency-medium/30">
            <p className="text-sm font-medium" style={{ color: 'hsl(var(--urgency-medium))' }}>{structural_risk.message}</p>
          </div>
        )}

        {/* ====== Gates ====== */}
        {gates && gates.length > 0 && gates.map((g, i) => (
          <div key={i} className="p-3 rounded-lg border bg-urgency-high/10 border-urgency-high/30">
            <p className="text-sm font-medium" style={{ color: 'hsl(var(--urgency-high))' }}>
              出愿资格不满足：{g.school} 要求 {g.required}，你只有 {g.current}
            </p>
          </div>
        ))}

        {/* ====== Two-column: Actions + Nearest Deadline ====== */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Next Actions (left) */}
          {next_actions && next_actions.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-foreground mb-2">建议行动</h3>
              <div className="space-y-1.5">
                {next_actions.map((a, i) => (
                  <button key={i}
                    onClick={() => onNavigate(a.tab, a.params || {})}
                    className="w-full flex items-center gap-3 p-3 rounded-lg border hover:bg-muted/50 transition text-left group"
                  >
                    <span className={`w-2 h-2 rounded-full shrink-0 ${a.priority === 'high' ? 'bg-urgency-high' : a.priority === 'medium' ? 'bg-urgency-medium' : 'bg-muted-foreground/30'}`} />
                    <span className="text-sm flex-1">{a.label}</span>
                    <span className="text-xs text-muted-foreground hidden sm:inline">{a.reason}</span>
                    <ChevronRight size={14} className="text-muted-foreground shrink-0 opacity-0 group-hover:opacity-100 transition" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Nearest Deadline (right) */}
          {nearestDl && (() => {
            const uc = urgencyClasses(nearestDl.days);
            return (
              <div>
                <h3 className="text-sm font-semibold text-foreground mb-2">最近截止日</h3>
                <div className={`p-4 rounded-xl border ${uc.bg} ${nearestDl.days <= 7 ? 'border-urgency-high/30' : nearestDl.days <= 14 ? 'border-urgency-medium/30' : 'border'}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <Calendar size={15} className={uc.text} />
                    <span className="text-sm font-semibold">{nearestDl.school}</span>
                  </div>
                  <div className="flex items-baseline gap-2 mb-3">
                    <span className="text-xs text-muted-foreground">{nearestDl.name}</span>
                    <span className={`text-lg font-bold tabular-nums ${uc.text}`}>
                      {nearestDl.days >= 0 ? `${nearestDl.days} 天后` : `已过期 ${Math.abs(nearestDl.days)} 天`}
                    </span>
                  </div>
                  {/* Progress bar */}
                  {nearestDl.days >= 0 && (
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${nearestDl.days <= 7 ? 'bg-urgency-high' : nearestDl.days <= 14 ? 'bg-urgency-medium' : 'bg-muted-foreground/30'}`}
                        style={{ width: `${Math.max(5, 100 - nearestDl.days * 3)}%` }}
                      />
                    </div>
                  )}
                </div>
              </div>
            );
          })()}
        </div>

        {/* ====== School Status Groups ====== */}
        {Object.keys(grouped).length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-foreground mb-3">志愿校状态</h3>
            <div className="space-y-2">
              {STAGE_ORDER.filter(s => grouped[s]).map(s => (
                <details key={s} className="border rounded-xl group">
                  <summary className="px-4 py-3 cursor-pointer text-sm font-medium flex items-center gap-3 select-none">
                    <span className={`w-1 h-6 rounded-full shrink-0`} style={{ backgroundColor: `hsl(var(--stage-${s}))` }} />
                    {STAGE_LABEL[s]}阶段
                    <span className="inline-flex items-center justify-center min-w-[22px] h-5 px-1.5 rounded-full text-xs bg-muted text-muted-foreground tabular-nums">
                      {grouped[s].length}
                    </span>
                    <ChevronRight size={14} className="text-muted-foreground ml-auto transition-transform group-open:rotate-90" />
                  </summary>
                  <div className="px-4 pb-3 space-y-1">
                    {grouped[s].map((app, i) => (
                      <div key={i} className="flex items-center justify-between py-1.5 border-t text-xs">
                        <span className="text-foreground/80 truncate max-w-[55%]">
                          {app.school}{app.major ? ` · ${app.major}` : ''}
                        </span>
                        <div className="flex items-center gap-2 shrink-0">
                          {app.professors?.length > 0 && (
                            <span className="text-muted-foreground">{app.professors.length}位教授</span>
                          )}
                          <span className="text-[10px] text-muted-foreground/60 bg-muted px-1.5 py-0.5 rounded">暂无口碑</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          </div>
        )}

        {/* ====== Empty schools (has some profile but no tracking) ====== */}
        {(!applications || applications.length === 0) && pc.filled > 0 && (
          <EmptyState
            icon={School}
            title="还没有追踪的学校"
            description="去学校广场发现适合你的目标校，开始追踪申请进度"
            action={{ label: '去广场', onClick: () => onNavigate('plaza') }}
          />
        )}

      </div>
    </div>
  );
}
