import streamlit as st
from user.profile_manager import ProfileManager, UserProfile
from agent.react_agent import ReactAgent
from agent.prompts import PLANNER_PROMPT

def render_main_app():
    # --- 0. 初始化基础组件 ---
    profile_mgr = st.session_state.get('profile_mgr')
    if profile_mgr is None:
        profile_mgr = ProfileManager()
        st.session_state['profile_mgr'] = profile_mgr

    # 定义 Agent 初始化辅助函数 (用于解耦和复用)
    def get_agent_instance():
        current_p = st.session_state.user_profile
        profile_dict = {
            "jlpt": current_p.jlpt_level,
            "eju": current_p.eju_score,
            "gpa": current_p.gpa,
            "major": current_p.target_major,
            "undergraduate_school": current_p.undergraduate_school,
            "english_score": current_p.english_score
        }
        return ReactAgent(user_profile=profile_dict)

    st.title("🌸 日本留学智能客服")
    
    # 顶部导航栏
    col1, col2 = st.columns([4, 1])
    with col1:
        st.caption(f"当前登录：{st.session_state.auth_user.email}")
    with col2:
        if st.button("退出登录", key="logout"):
            try:
                import extra_streamlit_components as stx
                cookie_manager = stx.CookieManager()
                cookie_manager.delete("sb_access_token")
                cookie_manager.delete("sb_refresh_token")
            except Exception:
                pass
            profile_mgr.supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()
    st.divider()

    current_user_id = st.session_state.auth_user.id

    # --- 1. 用户画像同步 ---
    if "user_profile" not in st.session_state:
        with st.spinner("正在同步云端画像..."):
            db_profile = profile_mgr.get_profile(current_user_id)
            st.session_state.user_profile = db_profile or UserProfile()

    # 首次运行欢迎语与报告看板拉取
    if "first_run" not in st.session_state:
        st.session_state.first_run = True
        
        # 检查是否有历史报告建议
        current_p = st.session_state.user_profile
        if current_p.report_status != "NONE" and current_p.suggestions:
            welcome_msg = (
                f"### 🌸 欢迎回来，{st.session_state.auth_user.email}！\n\n"
                f"我查阅了你之前的专属升学报告，当前报告状态为：**{current_p.report_status}**。\n\n"
                f"💡 **以下是为你定制的升学核心建议看板：**\n\n"
                f"{current_p.suggestions}\n\n"
                f"---\n"
                f"你可以直接针对上述某条建议提问（例如：'关于第一条建议，我该怎么做？'），"
                f"或者如果你觉得计划生变，可以直接告诉我，我会为你重新调整建议看板。"
            )
        else:
            welcome_msg = "### 欢迎回来！我已经准备好为你进行留学规划了。请在左侧补充你的背景信息以便我给出更精准的建议。"
            
        with st.chat_message("assistant"):
            st.markdown(welcome_msg)
            
        # 将欢迎语隐式加入到 messages 历史中（可选，这样用户刷新不会丢，但这里按照原逻辑先不加入session history，只做首屏展示，或者加入）
        if "messages" not in st.session_state:
            st.session_state["messages"] = []
        st.session_state["messages"].append({"role": "assistant", "content": welcome_msg})

    # --- 2. 侧边栏表单 (仅负责更新数据和销毁 Agent) ---
    with st.sidebar:
        st.header("🎓 留学生背景评估")
        current_p = st.session_state.user_profile
        
        with st.form("user_profile_form"):
            jlpt_options = ["无", "N5", "N4", "N3", "N2", "N1"]
            jlpt = st.selectbox("JLPT等级", jlpt_options, index=jlpt_options.index(current_p.jlpt_level))
            eju = st.number_input("EJU总分预估", 0, 800, value=int(current_p.eju_score))
            gpa = st.number_input("本科GPA", 0.0, 4.0, value=float(current_p.gpa), step=0.1)
            major = st.text_input("意向专业", value=current_p.target_major)
            school = st.text_input("本科院校", value=current_p.undergraduate_school)
            eng_score = st.text_input("英语成绩", value=current_p.english_score)
            
            submitted = st.form_submit_button("更新并保存画像")
            
            if submitted:
                updated_profile = UserProfile(
                    jlpt_level=jlpt, eju_score=eju, gpa=gpa,
                    target_major=major, undergraduate_school=school, english_score=eng_score,
                    # 继承原有的报告状态，防止表单提交时丢失
                    report_status=current_p.report_status,
                    suggestions=current_p.suggestions
                )
                profile_mgr.save_profile(current_user_id, updated_profile)
                st.session_state.user_profile = updated_profile
                
                # 关键：画像更新后销毁旧 Agent，下次对话会自动重建带新背景的 Agent
                if "agent" in st.session_state:
                    del st.session_state["agent"]
                st.success("✅ 背景已更新！")
                st.rerun()

    # --- 3. 布局分配: 仪表盘 vs 对話框 ---
    current_p = st.session_state.user_profile
    has_suggestions = current_p.report_status != "NONE" and current_p.suggestions

    if has_suggestions:
        col_dash, col_chat = st.columns([1, 1], gap="large")
    else:
        col_dash, col_chat = None, st.container()

    # --- 3.1 左侧：仪表盘 (Dashboard) ---
    if col_dash:
        with col_dash:
            st.subheader("📋 您的专属升学看板")
            st.info(f"当前进度状态：**{current_p.report_status}**")
            
            # 解析并渲染建议卡片 (假设建议是以分号或换行分隔的，这里做简单处理)
            suggestions_list = [s.strip() for s in current_p.suggestions.split('\n') if s.strip()]
            for i, suggestion in enumerate(suggestions_list):
                with st.container(border=True):
                    st.markdown(f"**建议 {i+1}**")
                    st.write(suggestion)
                    if st.button(f"🔍 展开咨询", key=f"ask_{i}"):
                        st.session_state.pending_prompt = f"针对我的第 {i+1} 条建议：'{suggestion}'，请给出更详细的执行步骤和注意事项。"

            st.divider()
            st.caption("💡 提示：点击建议卡片下方的按钮，Agent 会立即为你深度解读该项任务。")

    # --- 3.2 右侧：对话展示与交互 ---
    with (col_chat if col_chat else st.container()):
        if "messages" not in st.session_state:
            st.session_state["messages"] = []

        # 渲染历史消息
        for message in st.session_state["messages"]:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        # --- 4. 核心对话与决策逻辑 ---
        # 优先处理来自 Dashboard 的点击
        if "pending_prompt" in st.session_state:
            prompt = st.session_state.pop("pending_prompt")
        else:
            prompt = st.chat_input("请输入您的问题，或者点击左侧看板...")

        if prompt:
            # A. 确保 Agent 存在 (惰性加载)
            if "agent" not in st.session_state:
                st.session_state["agent"] = get_agent_instance()
            
            with st.chat_message("user"):
                st.write(prompt)
            st.session_state["messages"].append({"role": "user", "content": prompt})

            profile_string = profile_mgr.format_for_prompt(st.session_state.user_profile)

            # B. 决策引擎
            with st.status("💡 正在规划最佳路径...", expanded=False) as status:
                decision = st.session_state["agent"].make_decision(
                    PLANNER_PROMPT,
                    profile_string,
                    prompt
                )
                st.write(f"决策引擎输出: {decision}")
                
                if "[MISSING_INFO]" in decision:
                    st.warning("提示：完善侧边栏背景可以获得更准的建议哦！")
                status.update(label="规划完成", state="complete")

            # C. 执行流式对话
            try:
                with st.chat_message("assistant"):
                    res_stream = st.session_state["agent"].execute_stream(prompt, profile_string)
                    full_response = st.write_stream(res_stream)
                    
                    if full_response:
                        st.session_state["messages"].append({"role": "assistant", "content": full_response})
                        st.rerun()

            except Exception as e:
                st.error(f"处理中出错: {str(e)}")
                st.stop()