# Feature Spec: Onboarding Wizard — "Step 0" 探索向导

## Problem

现在的应用假设用户已经知道自己的研究方向。新用户登录后看到：

> "欢迎！我是你的日本升学顾问。告诉我你的研究方向，帮你匹配学校。"

但真实用户的第一步是：**"我有一个模糊的'想去日本读研'的念头，但什么都不确定。"**

Profile 系统（6 个字段 + facts + events + applications）是"被动填写"——用户得自己打开侧边栏一项项填。没有主动引导。

## Goal

做一个 **Step 0 探索向导**——AI 以留学顾问的身份，通过对话帮用户从"模糊念头"收敛到"2-3 个明确方向"。像聊天，不像填表。

## Non-goals

- 不做多步向导 UI（next/back 按钮、步骤条）
- 不改 Profile 数据模型
- 不加新的数据库表
- 不做 KAKEN/researchmap 教授搜索（那是另一个 feature）

---

## User Journey

### 入口

新用户（`profile_completeness.filled === 0`，无 applications）登录后，首页 dashboard 不再是现在的空白 empty state，而是直接**打开对话 tab**，AI 主动发出第一条消息开始探索对话。

具体触发条件：
- `filled <= 1`（最多填了 1 个字段）且 `applications.length === 0`
- 这种情况 `/v1/greeting` 返回 `onboarding: true, onboarding_phase: "start"`

返回用户（已填过 profile 或有 applications）不受影响，首页正常显示 dashboard。

### 对话流程（4 个 Phase）

AI 不强调"这是第 X 步"，而是在自然对话中完成 4 个阶段的探索。每个 phase 有明确的**目标信息**要收集，但通过聊天自然引出，不是表单式提问。

#### Phase 1: 了解现状（"你从哪里出发"）

**目标收集**：
- `undergraduate_school` — 本科学校
- `target_major` — 本科专业（推断目标专业方向）
- 年级/毕业时间（存入 `facts`）

**AI 开场示例**：
> "你好！我是你的日本升学顾问。先了解一下你的情况——你现在在读什么专业？大几了？"

用户回答后：
> "嗯，XX大学XX专业。那你为什么想去日本读研呢？是喜欢日本的文化，还是对某个领域特别感兴趣？"

**Phase 1 完成信号**：收集到本科学校 + 专业 + 毕业时间（至少 2/3）

#### Phase 2: 挖掘兴趣（"你对什么有热情"）

**目标收集**：
- `research_area` — 研究方向
- 兴趣强度/动机（存入 `facts`）

**AI 引导示例**：
> "你在XX专业里，有没有特别喜欢的方向或者课程？或者有没有什么话题，你愿意花一个下午去研究的？"

如果用户说不清楚：
> "那我给你几个方向参考一下——你看看哪个比较有感觉：\n1. 继续现在的XX方向，找对口的日本研究室\n2. 换个相关的方向，比如……（根据专业列举）\n3. 完全换个赛道，比如更偏应用/偏理论的\n不用马上决定，我们就聊聊。"

**Phase 2 完成信号**：用户表达了至少一个感兴趣的方向（research_area 非空）

#### Phase 3: 对标校准（"你大概在什么档位"）

**目标收集**：
- `gpa_score` + `gpa_scale` — 绩点
- `jlpt_level` — 日语水平
- `english_score` — 英语成绩
- 预算/国公立 vs 私立偏好（存入 `facts`）

**AI 引导示例**：
> "对 XX 方向感兴趣，那我们来对对条件。你现在日语和英语大概什么水平？绩点方便说吗？不用精确，大概就行。"

如果用户不知道自己的档位：
> "没关系。以你现在的背景（XX大学XX专业，GPA X.X），我给你对标几个档位的学校：\n- 冲刺档：东大/京大 级别的 XX 研究科\n- 匹配档：旧帝大/早庆 级别的 XX 研究科\n- 保底档：地方的国公立大学\n你觉得哪个档位是你想冲的？"

**Phase 3 完成信号**：收集到至少 2 项硬条件（日语/英语/GPA）

#### Phase 4: 方向收敛（"你的初步画像"）

**目标产出**：2-3 个明确的研究方向 + 对应的推荐档位

**AI 总结示例**：
> "好，我帮你总结一下目前的情况：\n\n- 背景：XX大学 XX专业 大三，GPA X.X\n- 日语：N2 / 英语：托福 85\n- 感兴趣的方向：XX、XX\n- 目标档位：旧帝大级别\n\n根据这些，我建议你先关注这两个方向：\n1. XX方向 — 比如 XX大学 XX研究科，XX教授\n2. XX方向 — 比如 XX大学 XX研究科\n\n要不要去广场看看这两个方向的学校？"

**Phase 4 完成信号**：AI 发出总结，用户确认或进入学校搜索

### 完成与衔接

当 Phase 4 完成（或 profile completeness >= 4/6，有 research_area），向导自动结束：

1. `/v1/greeting` 的 `onboarding` 变为 `false`
2. 首页恢复正常的 dashboard 视图（profile 完整度 ring + next actions + 学校推荐）
3. 如果用户在此期间添加了学校到追踪，侧边栏正常显示
4. 用户随时可以回到对话 tab 继续聊天——不再有特殊引导

### 跳过/中断

- 用户可以随时切换到其他 tab，向导不阻止
- 用户可以在对话中直接问学校、要匹配——AI 不强行拉回向导，正常回答
- 如果用户中途关掉再回来，greeting 根据当前 profile 状态判断是否需要继续

---

## Technical Design

### Backend

#### 1. Greeting 端点增强 (`/v1/greeting`)

在现有的 greeting 逻辑中增加 `onboarding` 判断：

```python
# 在 /v1/greeting 返回中加入
onboarding = (
    profile_completeness["filled"] <= 1
    and len(profile.applications) == 0
)

if onboarding:
    # 根据已收集的信息判断当前 phase
    phase = _onboarding_phase(profile, profile_completeness)
    greeting["onboarding"] = True
    greeting["onboarding_phase"] = phase  # "start" | "interests" | "calibrate" | "converge"
```

`_onboarding_phase()` 判断逻辑（纯规则，无 LLM）：
- `start`: research_area 为空，且 filled <= 1
- `interests`: 有本科信息但 research_area 为空
- `calibrate`: research_area 非空，但 jlpt/english/gpa 中 >= 2 项缺失
- `converge`: research_area 非空，且 >= 2 项硬条件已填
- 如果 filled >= 4 且有 research_area，返回 `None`（不触发 onboarding）

#### 2. 系统提示词增强（Chat pipeline）

在构建 chat 系统提示词时，如果用户处于 onboarding 模式，注入 `onboarding_instructions`：

```
你正在与一位刚开始规划日本留学的学生对话。学生目前的留学方向还不明确。
你的任务是：通过自然对话，帮他逐步理清方向。不要直接问"你想学什么"，而是从他不排斥的话题入手。

当前阶段：{phase}
已收集信息：{profile_summary}

引导原则：
- 每次只问 1-2 个问题，不要像问卷调查
- 先了解背景和兴趣，再问硬条件（成绩/语言/预算）
- 学生表示不确定时，给选项让他选，而不是继续追问
- 学生明确表达需求（如"帮我找学校"）时，立刻响应，不要强行拉回引导
- 用"我们"而不是"你"——"我们来看看"而不是"你应该"
```

实现位置：`agent/orchestrator.py` 的 `build_system_prompt()` 或等效位置。

#### 3. Intent 路由不受影响

`/v1/chat` 的现有 intent 分类和路由在 onboarding 期间正常工作——用户可以在向导中间问具体问题（"东大情报理工怎么样？"），系统正常走 search_schools/match/qa 路由。不新建 endpoint，不新建 intent。

### Frontend

#### 1. 首页行为变更

`App.jsx` 的 greeting 加载逻辑：

```jsx
// 在 loadGreeting 的 then 回调中
if (greeting.onboarding && !hasDismissedOnboarding) {
    setActiveTab('chat');  // 自动跳转到对话 tab
    // 不清空已有消息，greeting 消息正常显示
}
```

`hasDismissedOnboarding`：用户手动切换到其他 tab 后置为 true（localStorage），当次会话不再自动跳转。

#### 2. 对话页面的微调

- 不做新的 UI 组件
- greeting 消息作为对话的第一条消息正常渲染
- 用户在 onboarding 期间发送的消息，AI 正常回复
- 没有"第 X/4 步"的进度条（保持纯对话体验）

#### 3. Profile 面板行为不变

用户仍然可以随时打开侧边栏的 profile 面板手动填写。onboarding 对话中收集到的信息会自动反映在面板中（通过 `finish_turn` → `extract_facts_from_chat` → `merge_delta` 管道）。

### Edge Cases

| 场景 | 处理 |
|------|------|
| 用户注册后直接点广场 | 不强制跳转，但 dashboard 空状态文案改为"先跟 AI 聊聊你的情况？" |
| 用户在 Phase 1 就问"帮我找学校" | AI 自然回复"好的，不过我还不太了解你的情况。你是学什么专业的？"——不拒绝，但顺带收集信息 |
| 用户说"我不知道""随便" | AI 给 2-3 个选项让用户选，而不是继续追问 |
| 用户填了 profile 但没聊过天 | `filled >= 4` 时不触发 onboarding，正常显示 dashboard |
| 用户聊了一半，第二天再登录 | greeting 读 profile 状态，从对应 phase 继续 |

---

## Verification

### Manual

1. 用新账号（profile 全空）登录 → 首页应自动跳到对话 tab，AI 发送探索开场消息
2. 跟着 AI 的引导聊完 4 个 phase → profile 面板应显示收集到的信息
3. 聊到 research_area 非空 + 2 项硬条件后 → 再刷新，首页正常显示 dashboard 而非跳到对话
4. 在 Phase 1 中切换到广场 tab → 不自动跳回对话
5. 已填写 profile 的账号登录 → 不受影响，正常显示 dashboard

### API

```bash
# 新用户 greeting 应返回 onboarding: true
curl -H "Authorization: Bearer $TOKEN" /v1/greeting | jq '.onboarding'

# 完成 profile 后应返回 onboarding: false 或不返回该字段
```

---

## Summary

| 维度 | 决策 |
|------|------|
| 交互形式 | 纯对话，不做向导 UI |
| 触发条件 | profile filled <= 1 且无 applications |
| 后端改动 | `/v1/greeting` 加 onboarding 字段 + 系统提示词注入 |
| 前端改动 | 首页自动跳转到对话 tab（仅首次） |
| 新增 endpoint | 无 |
| 新增 intent | 无 |
| 数据模型 | 不变 |
| 实现周期 | 1-2 天 |
