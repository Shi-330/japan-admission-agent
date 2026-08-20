# Feature Spec: Visual Polish Pass — 面试展示优化

## Overview

功能密度已足够，现在给已有的功能"穿正装"。目标：面试官 30 秒内看到的截图/演示像一个真正的产品，而非学生 toy project。

四个发力点（按面试冲击力排序）：
1. Dashboard 首页重设计 — 登录后第一屏做成"指挥舱"
2. 统一 Design Tokens — 消灭所有硬编码颜色，建立视觉一致性
3. 空状态补完 — 每个 Tab 的空状态有引导、有质感
4. Demo 模式 — 一键注入示例数据，面试演示 30 秒就位

**不做的事**：不重写前端、不加新 Tab、不加新 API 端点（demo 模式除外）、不迁移组件库、不引入图表库。

---

## Component 1: Design Tokens — 统一颜色系统

### 1a: CSS 变量扩展 (`frontend/src/index.css`)

在 `:root` 中新增应用语义色：

```css
:root {
  /* 现有 shadcn tokens 保留 */

  /* —— 阶段色（stage）—— */
  --stage-preparing: 220 14% 55%;       /* 准备 — 蓝灰 */
  --stage-contacting: 152 30% 35%;       /* 套磁 — 绿 */
  --stage-applying: 260 15% 45%;         /* 出愿 — 紫 */
  --stage-exam: 35 40% 45%;              /* 考试 — 琥珀 */
  --stage-waiting: 30 28% 50%;           /* 等待 — 暖灰 */
  --stage-decided: 152 30% 32%;          /* 确定 — 深绿 */

  /* —— 紧急度色（deadline / severity）—— */
  --urgency-high: 0 72% 55%;             /* 红 — <=7天 / high */
  --urgency-medium: 38 75% 45%;          /* 琥珀 — <=14天 / medium */
  --urgency-low: 220 14% 55%;            /* 灰蓝 — >14天 / low */

  /* —— 教授状态色 —— */
  --prof-sent: 215 14% 50%;
  --prof-replied: 152 25% 38%;
  --prof-rejected: 6 45% 55%;
  --prof-noreply: 40 55% 48%;
  --prof-interview: 195 30% 45%;

  /* —— 品牌强调色（替代散落的 indigo）—— */
  --brand: 243 75% 60%;
  --brand-foreground: 0 0% 100%;
}
```

### 1b: Tailwind 配置扩展 (`frontend/tailwind.config.js`)

```js
colors: {
  stage: {
    preparing: 'hsl(var(--stage-preparing))',
    contacting: 'hsl(var(--stage-contacting))',
    applying: 'hsl(var(--stage-applying))',
    exam: 'hsl(var(--stage-exam))',
    waiting: 'hsl(var(--stage-waiting))',
    decided: 'hsl(var(--stage-decided))',
  },
  urgency: { high: 'hsl(var(--urgency-high))', medium: 'hsl(var(--urgency-medium))', low: 'hsl(var(--urgency-low))' },
  prof: { sent: 'hsl(var(--prof-sent))', replied: 'hsl(var(--prof-replied))', rejected: 'hsl(var(--prof-rejected))', noreply: 'hsl(var(--prof-noreply))', interview: 'hsl(var(--prof-interview))' },
  brand: { DEFAULT: 'hsl(var(--brand))', foreground: 'hsl(var(--brand-foreground))' },
}
```

### 1c: 替换现有硬编码颜色

| 文件 | 位置 | 旧值 | 新 token |
|------|------|------|----------|
| App.jsx | stageColors | `bg-[#E8F0EC]` 等 hex | `bg-stage-contacting/15 text-stage-contacting` 等 |
| App.jsx | profStatusColors | `text-[#5B6D8A]` 等 hex | `text-prof-sent` 等 |
| App.jsx | profStatusLabel | 枚举 | 不变（文本） |
| DashboardView.jsx | verdictColor | `text-amber-600` 等 | `text-urgency-high` 等 |
| DashboardView.jsx | nearestDl 条件 | `bg-red-50` 等 | `bg-urgency-high/10` 等 |
| ReminderDrawer.jsx | severity 左边框 | 硬编码红/琥珀/灰 | `border-l-urgency-high` 等 |
| CalendarView.jsx | deadline 圆点 | 硬编码色 | `bg-urgency-high` 等 |
| OutreachDraft.jsx | placeholder 高亮 | `bg-yellow-100` | 保留（这是内容高亮，非语义色） |

验收：
- `grep -r 'bg-\[#' frontend/src/` 返回空
- `grep -r 'text-\[#' frontend/src/` 返回空
- 所有 stage/severity/prof 颜色通过 CSS 变量可全局切换

---

## Component 2: Dashboard 首页重设计

### 目标

把"信息列表"升级为"指挥舱"。面试官第一眼看到的截图应该传达：这个系统在主动管理学生的申请。

### 2a: 布局重构

当前是单列 `max-w-4xl space-y-5`，改为双层结构：

```
┌──────────────────────────────────────────────┐
│  [问候语 banner]           [画像完整度 环形] │  ← Hero 区
│                             [快速补全]        │
├──────────────────────────────────────────────┤
│  [志愿校 12]  [截止日临近 3]  [需跟进 2]     │  ← KPI 卡片行
├──────────────────────────────────────────────┤
│  申请节奏                          本周行动  │  ← 时间线
│  ├ 京大 - 该套磁 ─ 田中2周未回               │
│  ├ 东工大 - 该复习 ─ 笔试8月                 │
│  └ 阪大 - 收尾出愿 ─ 截止12月                │
├────────────────────┬─────────────────────────┤
│  建议行动           │  最近截止日             │  ← 双栏
│  • 拟套磁信 →       │  京大 I期出愿            │
│  • 准备N1 →         │  12 天后                 │
│                     │  ━━━━━━━━━░░░ 78%       │
├────────────────────┴─────────────────────────┤
│  志愿校状态                                    │
│  ▸ 套磁中 (3)    ▸ 出愿中 (2)    ▸ 考试 (1)  │  ← 展开式分组
└──────────────────────────────────────────────┘
```

### 2b: 具体改动

**Hero 区（问候 + 画像环形进度）**

将现在的问候语 banner + 独立画像卡片合并为一行。左侧问候语（保持现有 amber 提醒色），右侧画像环形进度（用 SVG circle，替代现有线形进度条）：
- 中间大字显示百分比，环内显示 "8/10 项"
- 点击跳转编辑画像
- loading 态保留现有 spinner

**KPI 卡片行（3 张卡片）**

保持现有 3 卡片但视觉升级：
- 数字用 `text-3xl font-bold tabular-nums`（更大的等宽数字）
- 志愿校卡片：hover 显示"去广场"链接
- 截止日卡片：≤7 天整卡红底白字（而非仅文字变色），>7 天保持现状
- 提醒卡片：overdue 时整卡琥珀底 + 脉冲动画（`animate-pulse` 慢速），点击跳转提醒抽屉

**申请节奏区**

保持现有结构但视觉强化：
- verdict 标签从纯文字改为 pill 徽章（`rounded-full px-2 py-0.5`），颜色用 stage token
- 每行 hover 时右侧出现快捷动作图标（套磁图标 / 日历图标）
- reason 文字超过 30 字截断 + "..." + hover tooltip

**建议行动 + 最近截止日 → 双栏**

将现在上下排列的两区改为左右双栏：
- 左栏（建议行动）：保持现有列表，每条前的圆点改为对应紧急度的 icon
- 右栏（最近截止日）：不是纯文字，加一条倒计时进度条（`已过天数 / 总天数`），视觉上传达紧迫感

**志愿校状态 → 展开卡片**

将 `<details>` 改为展开式卡片组：
- 每个 stage 一张卡片，左侧色条（`border-l-4`）+ stage 名 + 学校数 badge
- 展开后显示该 stage 下的学校列表（小字），含教授状态摘要
- 点击学校名 → 切到对应 tab（与现有 `onNavigate` 一致）

**学校广场入口**

当无学校时，空状态加一张"发现适合你的学校"卡片，样式不同于纯文字空状态——大图/icon + 粗体引导文案 + 从 greeting 中提取的推荐专业关键词。

### 2c: 不变的部分

- API 调用不变（`/v1/greeting` 端点不改）
- Props 接口不变
- `greeting` 数据结构不变
- Framer Motion `AnimatePresence` 包裹方式不变

---

## Component 3: 空状态补完

### 统一空状态组件 (`frontend/src/components/EmptyState.jsx`)

提取一个可复用的空状态组件，替代各 Tab 内分散的空状态 JSX：

```jsx
<EmptyState
  icon={School}           // lucide icon
  title="还没有追踪的学校"
  description="去学校广场发现适合你的目标校，开始追踪申请进度"
  action={{ label: "去广场", onClick: () => onNavigate('plaza') }}
/>
```

Props: `icon`, `title`, `description`, `action?`（可选的按钮）。

### 各 Tab 空状态清单

| Tab | 现状 | 改进 |
|-----|------|------|
| 首页 | 两处空状态（无画像 / 无学校）| 合并为 EmptyState，无画像时优先展示 |
| 对话 | 初始空 chat（只有 greeting） | 加 suggested questions chips（已有概念但未在 chat 空态展示） |
| 广场 | 数据由 `/v1/schools` 返回，空时显示"未找到匹配学校" | 用 EmptyState 替代纯文字 |
| 日历 | "还没有追踪的学校" | 用 EmptyState |
| 文书 | "暂无存档草稿" | 用 EmptyState（已有较完整的空态，改为用共享组件） |

---

## Component 4: Demo 模式

### 4a: 后端 — Demo 数据注入端点

新增 `POST /v1/demo/seed` (JWT required)：

```python
# backend/api/server.py

@app.post("/v1/demo/seed")
async def demo_seed(profile: UserProfile = Depends(get_profile)):
    """Inject demo data: 3 tracked schools + 2 professors + 1 deadline + profile fields."""
    demo_profile = {
        "target_degree": "修士",
        "research_area": "自然语言处理",
        "jlpt_level": "N1",
        "gpa_score": 3.2,
        "gpa_scale": 4.0,
        "ielts": 7.0,
        "undergrad_school": "北京邮电大学",
        "undergrad_major": "计算机科学与技术",
        "applications": [
            {
                "school": "京都大学 情报理工学研究科",
                "stage": "contacting",
                "major": "知能情报学",
                "professors": [
                    {"name": "田中太郎", "status": "sent", "date": "2026-06-20"},
                    {"name": "山田花子", "status": "no_reply", "date": "2026-07-05"}
                ],
                "deadlines": {"I期出願": "2026-08-15", "II期出願": "2026-12-10"},
                "notes": "田中2周未回，已换山田。I期8月截止需抓紧。"
            },
            {
                "school": "东京工业大学 情报理工学院",
                "stage": "preparing",
                "major": "情报工学",
                "professors": [],
                "deadlines": {"夏季入试": "2026-09-01"},
                "notes": ""
            },
            {
                "school": "大阪大学 情报科学研究科",
                "stage": "applying",
                "major": "知能系统",
                "professors": [{"name": "中村健一", "status": "replied", "date": "2026-07-10"}],
                "deadlines": {"冬季出願": "2026-12-15"},
                "notes": "中村教授回复积极，建议申请"
            }
        ],
        "facts": {
            "dismissed_reminders": {},
            "demo_mode": True,
            "demo_injected_at": "auto"
        }
    }
    pm = ProfileManager()
    pm.merge_delta(profile, demo_profile)
    # Persist to Supabase
    ...
    return {"ok": True, "message": "Demo data injected. Reload to see full dashboard."}
```

要点：
- 幂等：重复调用覆盖而非追加（`upsert_application` 按 school name 去重）
- 可清除：`DELETE /v1/demo/seed` — 删除所有 `demo_mode: True` 的 applications + 清除 demo facts
- 不影响真实数据：注入的每条 application 携带 `"demo": True` 标记，前端可据此在编辑时给出提示

### 4b: 前端 — Demo 开关

在 Dashboard 首页右上角（或 sidebar 底部）加一个开关：

```
┌──────────────────────┐
│ 演示模式  [Switch]   │
└──────────────────────┘
```

行为：
- 首次登录且画像为空 → 自动弹出 toast："试试演示模式？一键填充示例数据" → 点击 toast 即注入
- 开关打开 → `fetch POST /v1/demo/seed` → toast 成功 → 刷新 profile + greeting
- 开关关闭 → `fetch DELETE /v1/demo/seed` → 恢复原有数据 → 刷新
- Demo 模式下，Dashboard 顶部显示浅蓝 banner："当前为演示数据，点击关闭演示模式恢复"

实现：
- 状态：`const [demoMode, setDemoMode] = useState(false)` 在 App.jsx
- 检测：profile 加载后检查 `profile.facts?.demo_mode`
- 开关显示条件：始终可见（方便面试时开关）
- localStorage 不持久化这个开关（每次登录重新检测）

### 4c: Demo 数据要求

注入的数据必须满足：
- 覆盖所有 stage（每校不同） → 面试时可以展示"志愿校状态"分组
- 有超期教授 → 提醒铃铛有内容
- 有近期截止日（注入时用 `today + N days` 动态计算，确保永远是未来日期）→ Dashboard 倒计时可见
- 画像完整度 > 50% → 环形图不空

---

## Acceptance Criteria

| # | 验收项 | 验证方式 |
|---|--------|---------|
| C1 | CSS 变量全部 `frontend/src/index.css` 中定义，`grep -r 'bg-\[' frontend/src/` 返回空 | grep |
| C2 | `tailwind.config.js` 注册 stage/urgency/prof/brand 色系，可 Tailwind intellisense | 手动 |
| C3 | Dashboard Hero 区环形进度图正常渲染，显示百分比 + X/Y 项 | 登录 test@example.com |
| C4 | KPI 卡片数字等宽字体、截止日 ≤7 天时整卡红底 | 注入 demo 数据后 |
| C5 | 申请节奏 verdict 文字改为 pill 徽章 | 截图对比 |
| C6 | 建议行动 + 最近截止日双栏布局，截止日含进度条 | 截图对比 |
| C7 | 志愿校状态从 `<details>` 改为展开卡片，左侧色条 | 截图对比 |
| C8 | `EmptyState.jsx` 组件存在且 5 个 Tab 至少 4 个使用它 | grep |
| C9 | `POST /v1/demo/seed` 返回 200，注入后 greeting 含 3 校、画像 > 50%、有提醒 | curl |
| C10 | `DELETE /v1/demo/seed` 清除 demo 数据，profile 恢复 | curl |
| C11 | 前端 demo 开关：打开→弹 toast→首页刷新；关闭→恢复→toast | 手动（这个需要你验收） |
| C12 | 空画像首次登录弹 toast "试试演示模式" | 手动 |
| C13 | Demo 模式下显示浅蓝 banner | 截图 |
| C14 | 所有 UI 文本不含 emoji | 全局目视 |
| C15 | 无控制台 error（React 渲染错误） | F12 Console |

---

## 文件变更清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `frontend/src/index.css` | 修改 | 新增 CSS 变量 |
| `frontend/tailwind.config.js` | 修改 | 注册新色系 |
| `frontend/src/components/DashboardView.jsx` | 重写 | 新布局 |
| `frontend/src/components/EmptyState.jsx` | 新建 | 共享空状态组件 |
| `frontend/src/App.jsx` | 修改 | 替换硬编码色、集成 demo 开关、空状态替换 |
| `frontend/src/components/ReminderDrawer.jsx` | 修改 | severity 色替换 |
| `frontend/src/components/CalendarView.jsx` | 修改 | deadline 色替换 |
| `frontend/src/components/DocumentsView.jsx` | 修改 | 空状态替换 |
| `frontend/src/components/OutreachDraft.jsx` | 修改 | 色替换（如有） |
| `backend/api/server.py` | 修改 | 新增 demo seed/delete 端点 |

## 不在 Scope

- 不引入 recharts/visx 等图表库（环形图用纯 SVG）
- 不改 shadcn/ui 组件本身
- 不加新 Tab 或新页面路由
- 不做响应式移动端适配
- 不做 dark mode 切换（`.dark` 类保留但暂不激活）
- 不碰 Streamlit 管理面板
