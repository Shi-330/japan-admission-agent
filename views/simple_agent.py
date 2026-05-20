"""
Simple 3-layer agent: action buttons → matching / RAG / chat → LLM synthesis.
No ReAct, no decision engine, no tool loops.
"""
import streamlit as st
from demo.matching_engine import StudentProfile, match_schools, generate_timeline
from rag.rag_service import RagSummarizeService
from model.factory import chat_model
from user.profile_manager import ProfileManager, UserProfile


# ── helpers ──

def _get_profile():
    p = st.session_state.user_profile
    return StudentProfile(
        jlpt_level=p.jlpt_level, eju_score=int(p.eju_score), gpa=float(p.gpa),
        target_major=p.target_major, english_score=p.english_score,
        undergraduate_school=p.undergraduate_school,
    )

def _profile_str():
    p = st.session_state.user_profile
    return f"JLPT {p.jlpt_level}, EJU {p.eju_score}, GPA {p.gpa}, 目标 {p.target_major or '未设置'}, 英语 {p.english_score or '无'}"


# ── main ──

def render_simple_agent():
    st.title("日本留学智能顾问")

    # --- sidebar ---
    profile_mgr = st.session_state.get("profile_mgr") or ProfileManager()
    st.session_state["profile_mgr"] = profile_mgr
    if "user_profile" not in st.session_state:
        st.session_state.user_profile = UserProfile()

    with st.sidebar:
        st.header("学生背景")
        current_p = st.session_state.user_profile
        with st.form("profile_form"):
            jlpt = st.selectbox("JLPT", ["无","N5","N4","N3","N2","N1"],
                                index=["无","N5","N4","N3","N2","N1"].index(current_p.jlpt_level))
            eju = st.number_input("EJU总分", 0, 800, int(current_p.eju_score))
            gpa = st.number_input("GPA", 0.0, 4.0, float(current_p.gpa), 0.1)
            major = st.text_input("目标专业", current_p.target_major)
            eng = st.text_input("英语成绩 (如 TOEFL 80)", current_p.english_score)
            if st.form_submit_button("保存背景"):
                st.session_state.user_profile = UserProfile(
                    jlpt_level=jlpt, eju_score=eju, gpa=gpa,
                    target_major=major, english_score=eng,
                    suggestions=current_p.suggestions, report_status=current_p.report_status,
                )
                st.success("已保存")
                st.rerun()

        # Quick profile summary
        st.caption(f"当前: {_profile_str()}")

    # --- action bar ---
    col1, col2, col3 = st.columns(3)
    with col1:
        btn_match = st.button("🔍 院校匹配", use_container_width=True,
                              help="根据你的背景，列出所有可报考的学校及差距分析")
    with col2:
        btn_qa = st.button("📚 知识库问答", use_container_width=True,
                           help="查询私塾内部资料，了解具体申请细节")
    with col3:
        btn_report = st.button("📋 生成规划", use_container_width=True,
                               help="生成完整升学方案，含时间线和建议")

    # Profile status indicator
    p = st.session_state.user_profile
    if not p.target_major or p.target_major.strip() == "":
        st.warning("请先在侧边栏填写「目标专业」并点击保存")
    else:
        st.info(f"当前背景：{_profile_str()}")

    st.divider()

    # --- chat ---
    if "messages_simple" not in st.session_state:
        st.session_state.messages_simple = []
        st.session_state.messages_simple.append({
            "role": "assistant",
            "content": "👋 你好！你可以点击上方按钮，或直接在下方输入问题。"
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
            # Free text: quick LLM intent classification
            intent_prompt = f"""判断意图，只输出一个词：
用户说："{prompt}"
背景：{_profile_str()}
输出: chat / match / report / qa"""
            try:
                resp = chat_model.invoke(intent_prompt)
                for i in ["chat", "match", "report", "qa"]:
                    if i in resp.content.lower():
                        intent = i; break
            except Exception:
                intent = "qa"

        profile = _get_profile()

        with st.chat_message("assistant"):
            response = ""

            if intent == "chat":
                resp = chat_model.invoke(
                    f"学生说：{user_text}。背景：{_profile_str()}。友好回复1-2句，引导使用上方按钮。")
                response = resp.content

            elif intent in ("match", "report"):
                with st.spinner("正在匹配院校..."):
                    matches = match_schools(profile)
                if not matches:
                    # Fallback: use LLM to recommend schools based on profile
                    with st.spinner("本地数据库未覆盖此专业，正在联网搜索..."):
                        fallback_prompt = f"""学生背景：{_profile_str()}
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
                        lines.append(f"{m.status_label} **{m.school_name}**")
                        for g in m.gaps:
                            lines.append(f"  {'✅' if g.met else '❌'} {g.field}: {g.required} → 你 {g.current}")
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
                        rag = RagSummarizeService()
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
                        rag = RagSummarizeService()
                        rag_note = rag.get_raw_vector_context(user_text)
                    except Exception:
                        pass

                with st.spinner("生成回答..."):
                    llm_prompt = f"""你是日本升学顾问。

【资料】{rag_note if rag_note and len(rag_note) > 20 else "无"}
【学生】{_profile_str()}
【问题】{user_text}

简洁中文回答。资料为空则说明「知识库暂无相关内容」，基于公开信息回答但要标明。"""
                    try:
                        response = chat_model.invoke(llm_prompt).content
                    except Exception as e:
                        response = f"生成失败: {e}"

            st.write(response)
            st.session_state.messages_simple.append({"role": "assistant", "content": response})
