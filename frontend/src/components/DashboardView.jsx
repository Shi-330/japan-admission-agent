import { Loader2, ChevronRight, Bell, Calendar, School, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export default function DashboardView({ greeting, applications, profile, loading, onNavigate, onEditProfile }) {
  if (loading || !greeting) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">加载中...</span>
      </div>
    );
  }

  const { message, has_reminders, profile_completeness, next_actions, counts, when: whenArr, structural_risk, gates } = greeting;
  const pc = profile_completeness || { filled: 0, total: 6, percentage: 0 };

  // Empty profile — guide card
  if (pc.filled === 0 && (!applications || applications.length === 0)) {
    return (
      <div className="flex-1 overflow-y-auto p-6 flex items-center justify-center">
        <Card className="max-w-md w-full">
          <CardContent className="p-6 text-center">
            <User size={32} className="mx-auto mb-3 text-muted-foreground" />
            <h3 className="text-lg font-semibold mb-2">填写背景信息，开启个性化推荐</h3>
            <p className="text-sm text-muted-foreground mb-4">
              完善以下信息，获取精准的学校匹配和申请建议：
            </p>
            <ul className="text-sm text-left text-muted-foreground mb-4 space-y-1">
              <li>- 日语能力 (JLPT)</li>
              <li>- 英语成绩 (TOEFL/TOEIC)</li>
              <li>- GPA</li>
              <li>- 本科院校</li>
              <li>- 目标专业</li>
              <li>- 研究方向</li>
            </ul>
            <Button onClick={onEditProfile} className="w-full">去填写</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const verdictColor = (v) => ({
    '该套磁': 'text-amber-600',
    '套磁中': 'text-blue-600',
    '该复习': 'text-blue-600',
    '收尾出愿': 'text-red-600',
    '已考完/等待': 'text-gray-500',
    '还早': 'text-gray-400',
  })[v] || 'text-muted-foreground';

  // School status by stage
  const stages = ['preparing', 'contacting', 'applying', 'exam', 'waiting', 'decided'];
  const stageLabels = { preparing: '准备', contacting: '套磁', applying: '出愿', exam: '考试', waiting: '等待', decided: '确定' };
  const grouped = {};
  for (const s of stages) {
    const apps = (applications || []).filter(a => (a.stage_id || a.stage) === s);
    if (apps.length > 0) grouped[s] = apps;
  }

  // Nearest deadline
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

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto space-y-5">

        {/* Greeting */}
        <div className={`p-4 rounded-xl ${has_reminders ? 'bg-amber-50 border border-amber-200' : 'bg-card border'}`}>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message}</p>
        </div>

        {/* 时相脊椎 — 最显眼区域 */}
        {whenArr && whenArr.length > 0 && (
          <div className="border rounded-xl overflow-hidden">
            <div className="bg-card px-4 py-2.5 border-b flex items-center gap-2">
              <span className="text-sm font-semibold">申请节奏</span>
              <span className="text-xs text-muted-foreground">本周行动指南</span>
            </div>
            <div className="divide-y">
              {whenArr.map((item, i) => (
                <div key={i} className="px-4 py-3 flex items-center justify-between hover:bg-muted/30 transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-sm font-medium truncate">{item.school}</span>
                    {item.major && <span className="text-xs text-muted-foreground shrink-0">{item.major}</span>}
                    <span className={`text-sm font-bold shrink-0 ${verdictColor(item.verdict)}`}>{item.verdict}</span>
                  </div>
                  <span className="text-xs text-muted-foreground text-right shrink-0 ml-4 max-w-xs truncate">{item.reason}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Structural risk */}
        {structural_risk && (
          <div className="p-3 rounded-lg border bg-amber-50 border-amber-200">
            <p className="text-sm text-amber-800">{structural_risk.message}</p>
          </div>
        )}

        {/* Gates — 出愿资格不满足 */}
        {gates && gates.length > 0 && gates.map((g, i) => (
          <div key={i} className="p-3 rounded-lg border bg-red-50 border-red-200">
            <p className="text-sm text-red-800">出愿资格不满足：{g.school} 要求 {g.required}，你只有 {g.current}</p>
          </div>
        ))}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Profile completeness */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <User size={14} className="text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground">画像完整度</span>
              </div>
              <div className="text-xs text-muted-foreground mb-1">{pc.filled}/{pc.total} 项 · {pc.percentage}%</div>
              <div className="h-1.5 bg-gray-100 rounded-full">
                <div className="h-full bg-indigo-500 rounded-full transition-all" style={{ width: `${pc.percentage}%` }} />
              </div>
              {pc.percentage < 100 && (
                <button onClick={onEditProfile} className="text-xs text-indigo-500 hover:underline mt-1">去完善</button>
              )}
            </CardContent>
          </Card>

          {/* School count */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <School size={14} className="text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground">志愿校</span>
              </div>
              <div className="text-2xl font-bold mb-1">{counts.total_apps}</div>
              <div className="text-xs text-muted-foreground">
                {counts.upcoming_deadlines > 0 ? `${counts.upcoming_deadlines} 个截止日临近` : '暂无临近截止日'}
              </div>
            </CardContent>
          </Card>

          {/* Alerts */}
          <Card className={counts.overdue_profs > 0 ? 'bg-red-50 border-red-200' : ''}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Bell size={14} className={counts.overdue_profs > 0 ? 'text-red-500' : 'text-muted-foreground'} />
                <span className="text-xs font-medium text-muted-foreground">提醒</span>
              </div>
              <div className={`text-2xl font-bold mb-1 ${counts.overdue_profs > 0 ? 'text-red-600' : ''}`}>{counts.overdue_profs + counts.upcoming_deadlines}</div>
              <div className={`text-xs ${counts.overdue_profs > 0 ? 'text-red-600' : 'text-muted-foreground'}`}>
                {counts.overdue_profs > 0 ? `${counts.overdue_profs} 教授超期` : ''}
                {counts.overdue_profs > 0 && counts.upcoming_deadlines > 0 ? ' / ' : ''}
                {counts.upcoming_deadlines > 0 ? `${counts.upcoming_deadlines} 截止日` : ''}
                {counts.overdue_profs === 0 && counts.upcoming_deadlines === 0 ? '一切顺利' : ''}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Next actions */}
        {next_actions && next_actions.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-muted-foreground mb-2">建议行动</h3>
            <div className="space-y-1">
              {next_actions.map((a, i) => (
                <button key={i}
                  onClick={() => onNavigate(a.tab, a.params || {})}
                  className="w-full flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition text-left">
                  <div>
                    <span className={`inline-block w-1.5 h-1.5 rounded-full mr-2 ${a.priority === 'high' ? 'bg-amber-500' : 'bg-gray-300'}`} />
                    <span className="text-sm">{a.label}</span>
                    <span className="text-xs text-muted-foreground ml-2">{a.reason}</span>
                  </div>
                  <ChevronRight size={14} className="text-muted-foreground shrink-0" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Nearest deadline */}
        {nearestDl && (
          <div className={`p-3 rounded-lg border ${nearestDl.days <= 7 ? 'bg-red-50 border-red-200' : nearestDl.days <= 14 ? 'bg-amber-50 border-amber-200' : 'bg-card'}`}>
            <div className="flex items-center gap-2">
              <Calendar size={14} className={nearestDl.days <= 7 ? 'text-red-500' : 'text-amber-500'} />
              <span className="text-sm font-medium">
                {nearestDl.school} - {nearestDl.name}
              </span>
              <span className={`text-sm font-bold ${nearestDl.days <= 7 ? 'text-red-600' : nearestDl.days <= 14 ? 'text-amber-600' : 'text-muted-foreground'}`}>
                {nearestDl.days >= 0 ? `${nearestDl.days} 天后` : `已过期 ${Math.abs(nearestDl.days)} 天`}
              </span>
            </div>
          </div>
        )}

        {/* School status groups */}
        {Object.keys(grouped).length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-muted-foreground mb-2">志愿校状态</h3>
            <div className="space-y-2">
              {stages.filter(s => grouped[s]).map(s => (
                <details key={s} className="border rounded-lg">
                  <summary className="p-3 cursor-pointer text-sm font-medium">
                    {stageLabels[s]}阶段 ({grouped[s].length})
                  </summary>
                  <div className="px-3 pb-3 space-y-1">
                    {grouped[s].map((app, i) => (
                      <div key={i} className="text-xs text-muted-foreground flex items-center justify-between py-1 border-t">
                        <span>{app.school}{app.major ? ` - ${app.major}` : ''}</span>
                        <div className="flex items-center gap-2">
                          <span className="inline-block px-1.5 py-0.5 rounded text-[10px] bg-gray-100 text-gray-400 border">暂无口碑</span>
                          {app.professors?.length > 0 && <span>{app.professors.length} 位教授</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          </div>
        )}

        {/* Empty schools */}
        {(!applications || applications.length === 0) && (
          <div className="text-center py-8 border rounded-xl">
            <School size={24} className="mx-auto mb-2 text-muted-foreground" />
            <p className="text-sm text-muted-foreground mb-2">还没有追踪的学校</p>
            <Button onClick={() => onNavigate('plaza')} size="sm" variant="outline">去广场</Button>
          </div>
        )}

      </div>
    </div>
  );
}
