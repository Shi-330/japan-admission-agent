# ROADMAP — 当前状态与目标

> 唯一权威的「当前状态 / 目标 / 下一步」来源。其他文件(SPRINT_HISTORY、BACKLOG、specs、CLAUDE.md)一律指向这里。
> 活文档:只在**这里**更新"下一步",不要再开第二份清单(见 CLAUDE.md「Documentation Governance」)。

---

## 目标(待定)

> **TODO(待拍板)**:商业化方向未定 —— 卖给私塾(B2B) vs 直接卖给学生增值服务(B2C),还是分阶段。
> 现状矛盾:`docs/project-narrative.md` 写 B2B(卖给私塾减人效),`BACKLOG.md` 写 B2C(套磁精修 ¥19)。
> 先定锚,再回填这一段。

北极星:**agent 从"被动回答"进化到"替你执行"(agent-as-doer)**;护城河 = 私有数据(教授库 / 学校库 / 案例库)。

---

## 当前状态

### 已完成

- V2.1 Profile 2.0(facts / events / field_sources / gpa_scale / 事实抽取)
- V2.2 状态机(每校 stage + 每教授独立联系状态)
- V2.4 混合搜索(/v1/schools/search,RAG + BM25 + RRF + CN-JP 归一化)
- V2.5 前端 Dashboard(时相脊椎 + 结构风控)
- V2.7 Visual Polish(design tokens / demo mode / EmptyState)
- 学术层级(109 大学 + 396 研究科,4 层 schema)
- FastAPI + Auth(8 端点 + JWT)
- React 前端(login / chat / profile / stage / plaza / calendar)
- 部署(ECS + nginx + certbot,agent.shi330.xyz)
- 套磁草稿生成 V1(/v1/draft/outreach + OutreachDraft + DocumentsView)
- 主动提醒中心(ReminderBell / ReminderDrawer / /v1/reminders)
- Onboarding wizard(Step 0 引导)
- 前端 refactor(shadcn/ui / 主题系统 / 折叠侧栏)

### 进行中

- V2.3 私有库:学术层级已做;**案例库待补**(需真实用户结果飞轮,不靠编)

### 待办(去重后)

**A. 工程优化**(输入 / 输出 / 完成标准见 `specs/optimization-todo.md`)

1. 自动入库隔离 pending_review(P0)
2. cn2jp_normalize 缓存
3. 事实抽取惰性化
4. 删死代码(旧 ReAct 链路)
5. 抽 intent handlers(拆巨石)
6. RAG 检索评测(含 threshold 0.5→0.3 修复 + similarity 展示 bug)

**B. 产品闭环**(目标锚拍板后启动)

- V2.6 邮件自动化(OAuth + 发信 + 追踪)—— 对外动作,需 confirm + 追踪
- V2.3 案例库(数据护城河)

**C. 数据 / 依赖**

- requirements.txt 补 `sentence-transformers`(local embedding 依赖,BACKLOG P1)

**D. 前端遗留**(`specs/sprint-plan.md` 4 个 sprint 未落地)

- 侧栏卡片 countdown 标签(App.jsx 当前无)
- ChatMessage 富文本渲染(列表 / 表格 / 链接)+ 建议 follow-up chips
- Calendar 月份导航(左右箭头 + "今天";当前仍为固定 10 个月视图)

**E. 待人工验证**

- Sprint 1 eval 3 项 AC(加教授 / 加截止日 / 编辑备注,疑似 selector 问题)+ AC2(alert→toast)

---

## 下一步(优先级)

1. **自动入库隔离(P0)** —— 止血,风险最高、改动最小
2. **cn2jp 缓存 + 事实抽取惰性化** —— 立即降成本 / 延迟
3. **删死代码 + 抽 intent handlers** —— 给后续提速
4. **RAG 检索评测** —— 先有尺子再改 RAG

(以上 6 项 DoD 见 `specs/optimization-todo.md`)
