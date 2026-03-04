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

    # 首次运行欢迎语
    if "first_run" not in st.session_state:
        with st.chat_message("assistant"):
            st.markdown(f"### 欢迎回来！我已经准备好为你进行留学规划了。")
        st.session_state.first_run = True

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
                    target_major=major, undergraduate_school=school, english_score=eng_score
                )
                profile_mgr.save_profile(current_user_id, updated_profile)
                st.session_state.user_profile = updated_profile
                
                # 关键：画像更新后销毁旧 Agent，下次对话会自动重建带新背景的 Agent
                if "agent" in st.session_state:
                    del st.session_state["agent"]
                st.success("✅ 背景已更新！")
                st.rerun()

    # --- 3. 对话展示区域 ---
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for message in st.session_state["messages"]:
        st.chat_message(message["role"]).write(message["content"])

    # --- 4. 核心对话与决策逻辑 ---
    prompt = st.chat_input("请输入您的问题，例如：如何准备东京大学的面试？")

    if prompt:
        # A. 确保 Agent 存在 (惰性加载)
        if "agent" not in st.session_state:
            st.session_state["agent"] = get_agent_instance()
        
        st.chat_message("user").write(prompt)
        st.session_state["messages"].append({"role": "user", "content": prompt})

        profile_string = profile_mgr.format_for_prompt(st.session_state.user_profile)
        response_messages = []

        # B. 决策引擎 (已解耦，不再传入 external_cache)
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
                
                def capture_and_render(gen):
                    full_text = ""
                    for chunk in gen:
                        full_text += chunk
                        yield chunk
                    return full_text

                # 使用 st.write_stream 渲染并收集结果
                full_response = st.write_stream(res_stream)
                
                if full_response:
                    st.session_state["messages"].append({"role": "assistant", "content": full_response})
                    st.rerun()

        except Exception as e:
            st.error(f"处理中出错: {str(e)}")
            st.stop()