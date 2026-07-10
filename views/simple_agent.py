"""
Simple 3-layer agent: action buttons → matching / RAG / chat → LLM synthesis.
No ReAct, no decision engine, no tool loops.
"""
import streamlit as st
from demo.matching_engine import StudentProfile, match_schools, generate_timeline, STATUS_LABELS
from rag.rag_service import RagSummarizeService
from model.factory import chat_model
from user.profile_manager import ProfileManager, UserProfile
from agent.orchestrator import ChatOrchestrator
from agent.intent_layer import IntentLayerEngine, is_short_query


# ── helpers ──

def _get_profile():
    p = st.session_state.user_profile
    return StudentProfile(
        jlpt_level=p.jlpt_level, eju_score=int(p.eju_score), gpa=float(p.gpa),
        target_major=p.target_major, english_score=p.english_score,
        undergraduate_school=p.undergraduate_school,
    )


def _profile_str(profile_mgr=None):
    p = st.session_state.user_profile
    if profile_mgr:
        return profile_mgr.format_for_prompt(p)
    return f"JLPT {p.jlpt_level}, 目标 {p.target_major or '未设置'}, 英语 {p.english_score or '无'}"


def _get_orchestrator():
    if "_orchestrator" not in st.session_state:
        st.session_state._orchestrator = ChatOrchestrator()
    return st.session_state._orchestrator


# ── lazy RAG singleton (created once per session, not per request) ──
def _get_rag():
    if "_rag_service" not in st.session_state:
        st.session_state._rag_service = RagSummarizeService()
    return st.session_state._rag_service


# ── main ──

def render_simple_agent():
    st.title("日本留学智能顾问")

    # --- sidebar ---
    profile_mgr = st.session_state.get("profile_mgr") or ProfileManager()
    st.session_state["profile_mgr"] = profile_mgr
    current_user_id = st.session_state.auth_user.id

    if "user_profile" not in st.session_state:
        with st.spinner("正在同步云端画像..."):
            db_profile = profile_mgr.get_profile(current_user_id)
            st.session_state.user_profile = db_profile or UserProfile()

    with st.sidebar:
        # --- Quick actions (always visible) ---
        st.subheader("快捷操作")
        btn_match = st.button("院校匹配", use_container_width=True)
        btn_qa = st.button("知识库问答", use_container_width=True)
        btn_report = st.button("生成规划", use_container_width=True)
        st.divider()

        # --- Profile form ---
        st.subheader("学生背景")
        current_p = st.session_state.user_profile
        with st.form("profile_form"):
            st.caption(f"学位: {current_p.target_degree}")
            jlpt = st.selectbox("JLPT", ["无","N5","N4","N3","N2","N1"],
                                index=["无","N5","N4","N3","N2","N1"].index(current_p.jlpt_level)
                                if current_p.jlpt_level in ["无","N5","N4","N3","N2","N1"] else 0)
            eng = st.text_input("英语成绩 (如 TOEFL 95)", current_p.english_score)
            col1, col2 = st.columns(2)
            with col1:
                gpa_score = st.number_input("GPA", 0.0, 5.0, float(current_p.gpa_score), 0.1)
            with col2:
                gpa_scale = st.selectbox("满绩", [4.0, 4.3, 5.0, 100.0],
                    index=[4.0,4.3,5.0,100.0].index(current_p.gpa_scale)
                    if current_p.gpa_scale in [4.0,4.3,5.0,100.0] else 0)
            major = st.text_input("目标专业", current_p.target_major)
            research = st.text_input("研究方向", current_p.research_area,
                                     placeholder="如: 自然语言处理 / 地震工学")
            school = st.text_input("本科院校", current_p.undergraduate_school)
            if st.form_submit_button("保存背景"):
                updated = UserProfile(
                    jlpt_level=jlpt, english_score=eng,
                    gpa_score=gpa_score, gpa_scale=gpa_scale,
                    target_major=major, research_area=research,
                    undergraduate_school=school,
                    facts=current_p.facts, events=current_p.events,
                    target_professors=current_p.target_professors,
                    application_stage=current_p.application_stage,
                    field_sources=current_p.field_sources,
                    suggestions=current_p.suggestions, report_status=current_p.report_status,
                )
                for f in ["jlpt_level","english_score","target_major","research_area",
                          "undergraduate_school","gpa_score","gpa_scale"]:
                    updated.field_sources[f] = {"source": "form", "at": __import__('datetime').datetime.now().isoformat()}
                st.session_state.user_profile = updated
                profile_mgr.save_profile(current_user_id, updated)
                st.success("已保存")
                st.rerun()

        # Show AI-learned facts
        with st.expander("AI 已记录", expanded=False):
            if current_p.facts:
                for k, v in current_p.facts.items():
                    st.caption(f"{k}: {v}")
            if current_p.events:
                st.caption("--- 时间线 ---")
                for e in current_p.events[-5:]:
                    st.caption(f"{e['date']} | {e['event']}")
            if not current_p.facts and not current_p.events:
                st.caption("对话中 AI 会自动记录你的经历和重要节点")
        st.caption(f"当前: {_profile_str(profile_mgr)}")

    # --- main area ---
    p = st.session_state.user_profile
    if not p.target_major or p.target_major.strip() == "":
        st.warning("请先在侧边栏填写「目标专业」并点击保存")
    else:
        st.info(f"当前背景：{_profile_str(profile_mgr)}，点击侧边栏按钮或直接输入问题")

    st.divider()

    # --- chat ---
    if "messages_simple" not in st.session_state:
        st.session_state.messages_simple = []
        st.session_state.messages_simple.append({
            "role": "assistant",
            "content": "你好！你可以点击上方按钮，或直接在下方输入问题。"
        })

    for msg in st.session_state.messages_simple:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Handle button clicks via session state
    triggered = None
    if btn_match:
        triggered = "match"
    elif btn_qa:
        triggered = "qa"
    elif btn_report:
        triggered = "report"

    prompt = st.chat_input("或直接输入你的问题...")

    if triggered or prompt:
        user_text = prompt or {"match": "帮我看看能报考哪些学校",
                               "qa": "请根据我的背景给我一些申请建议",
                               "report": "请为我生成一份完整的升学规划报告"}[triggered]

        st.session_state.messages_simple.append({"role": "user", "content": user_text})
        with st.chat_message("user"):
            st.write(user_text)

        intent = triggered or "chat"
        if not triggered and prompt:
            # Short-query fast path: simple questions skip LLM classification
            if is_short_query(prompt):
                intent = "chat"
            else:
                engine = IntentLayerEngine()  # no catalog needed for intent only
                result = engine.classify(prompt, [], _profile_str(profile_mgr), "", chat_model)
                intent = result["intent"]

        profile = _get_profile()

        with st.chat_message("assistant"):
            response = ""

            if intent == "chat":
                resp = chat_model.invoke(
                    f"学生说：{user_text}。背景：{_profile_str(profile_mgr)}。友好回复1-2句，直接给出建议，不要指引用户去点击按钮。")
                response = resp.content

            elif intent in ("match", "report"):
                with st.spinner("正在匹配院校..."):
                    matches = match_schools(profile)
                if not matches:
                    # Fallback: use LLM to recommend schools based on profile
                    with st.spinner("本地数据库未覆盖此专业，正在联网搜索..."):
                        fallback_prompt = f"""学生背景：{_profile_str(profile_mgr)}
请根据这个背景，推荐3-5所日本大学（修士/硕士课程），每所说明：
- 学校和研究科名称
- JLPT/EJU/英语大致要求
- 考试形式
- 竞争难度
用简洁中文回答。开头说明「以下为联网搜索建议，非本地数据库精确匹配」。"""
                        try:
                            response = chat_model.invoke(fallback_prompt).content
                        except Exception as e:
                            response = f"本地数据库未覆盖「{profile.target_major}」专业，且联网搜索失败: {e}"
                else:
                    lines = ["## 院校匹配结果\n"]
                    for m in matches:
                        lines.append(f"{STATUS_LABELS[m.status]} **{m.school_name}**")
                        for g in m.gaps:
                            lines.append(f"  {'[O]' if g.met else '[X]'} {g.field}: {g.required} -> 你 {g.current}")
                        lines.append(f"  考试: {m.exam_info}")
                        lines.append(f"  {m.notes}\n")

                    if intent == "report":
                        lines.append("## 时间线\n")
                        for e in generate_timeline(matches):
                            lines.append(f"- {e}")

                    context = "\n".join(lines)

                    # RAG
                    rag_note = ""
                    try:
                        rag = _get_rag()
                        top = matches[0].school_name if matches else ""
                        r = rag.get_raw_vector_context(f"{top} {profile.target_major} 考试 面试 经验")
                        if r and len(r.strip()) > 20:
                            rag_note = f"\n\n## 内部经验\n{r[:600]}"
                    except Exception:
                        pass

                    # LLM synthesis
                    with st.spinner("正在生成建议..."):
                        llm_prompt = f"""根据以下信息给3-5句建议。

{context}
{rag_note}

简洁中文。"""
                        try:
                            resp = chat_model.invoke(llm_prompt)
                            response = context + rag_note + f"\n\n---\n## 综合建议\n{resp.content}"
                        except Exception:
                            response = context + rag_note + "\n\n(综合建议暂不可用)"

            else:  # qa
                with st.spinner("检索知识库..."):
                    rag_note = ""
                    try:
                        rag = _get_rag()
                        rag_note = rag.get_raw_vector_context(user_text)
                    except Exception:
                        pass

                with st.spinner("生成回答..."):
                    llm_prompt = f"""你是日本升学顾问。

【资料】{rag_note if rag_note and len(rag_note) > 20 else "无"}
【学生】{_profile_str(profile_mgr)}
【问题】{user_text}

简洁中文回答。资料为空则说明「知识库暂无相关内容」，基于公开信息回答但要标明。"""
                    try:
                        response = chat_model.invoke(llm_prompt).content
                    except Exception as e:
                        response = f"生成失败: {e}"

            st.write(response)
            st.session_state.messages_simple.append({"role": "assistant", "content": response})

            # V2.1: extract & merge new facts from this turn
            orch = _get_orchestrator()
            st.session_state.user_profile = orch.finish_turn(
                current_user_id, st.session_state.user_profile,
                user_text, response, chat_model)
