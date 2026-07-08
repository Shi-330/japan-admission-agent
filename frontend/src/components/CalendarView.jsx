function getMonths() {
  const now = new Date()
  const months = []
  for (let i = -1; i <= 8; i++) {
    months.push(new Date(now.getFullYear(), now.getMonth() + i, 1))
  }
  return months
}

function getDeadlineDates(deadlines) {
  if (!deadlines) return []
  const dots = []
  Object.entries(deadlines).forEach(([k, v]) => {
    try {
      const ds = String(v).split(/[~～]/)[0].trim().replace(/[年月]/g, '-').replace(/[日]/g, '')
      const d = new Date(ds)
      if (!isNaN(d.getTime())) {
        dots.push({ label: k, date: d, ds })
      }
    } catch {}
  })
  return dots
}

export default function CalendarView({ applications }) {
  if (!applications?.length) {
    return (
      <div className="flex-1 overflow-y-auto p-6 flex items-center justify-center">
        <p className="text-sm text-muted-foreground">还没有追踪的学校，去「广场」添加吧</p>
      </div>
    )
  }

  const now = new Date()
  const months = getMonths()
  let lastYear = null

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <h2 className="text-lg font-bold text-foreground mb-4">申请日历</h2>
      <div className="overflow-x-auto -mx-6 px-6">
        <div className="flex min-w-[900px]">
          {/* School column */}
          <div className="w-40 shrink-0">
            <div className="h-10" />
            {applications.map((app, i) => (
              <div key={i} className="h-16 flex items-center text-xs font-medium text-foreground border-b border-border pr-3 truncate">
                {app.school}
              </div>
            ))}
          </div>
          {/* Month columns */}
          <div className="flex-1 flex">
            {months.map((m, mi) => {
              const isCurrent = m.getMonth() === now.getMonth() && m.getFullYear() === now.getFullYear()
              const showYear = m.getFullYear() !== lastYear
              lastYear = m.getFullYear()
              return (
                <div key={mi} className={`flex-1 min-w-[64px] border-l border-border ${isCurrent ? 'bg-muted/50' : ''}`}>
                  <div className={`h-10 text-center pt-1.5 font-medium ${isCurrent ? 'text-foreground' : 'text-muted-foreground'}`}>
                    {showYear && <div className="text-[10px] leading-tight tabular-nums">{m.getFullYear()}</div>}
                    <div className="text-xs tabular-nums">{m.getMonth() + 1}月</div>
                  </div>
                  {applications.map((app, ai) => {
                    const dots = getDeadlineDates(app.deadlines).filter(
                      d => d.date.getMonth() === m.getMonth() && d.date.getFullYear() === m.getFullYear()
                    )
                    return (
                      <div key={ai} className="h-16 border-b border-border relative">
                        {dots.map((dot, di) => (
                          <div key={di}
                            className="absolute left-0.5 right-0.5 text-[10px] px-1 py-0.5 rounded bg-red-100 text-red-700 truncate font-medium"
                            style={{ top: `${3 + di * 18}px` }}
                            title={`${dot.label}: ${dot.ds}`}
                          >
                            {dot.label}
                          </div>
                        ))}
                      </div>
                    )
                  })}
                </div>
              )
            })}
          </div>
        </div>
        <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-red-100 inline-block" /> 截止日</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-muted/50 border border-border inline-block" /> 本月</span>
          <span className="text-muted-foreground/60">← 左右滑动 →</span>
        </div>
      </div>
    </div>
  )
}
