import streamlit as st
from user.profile_manager import ProfileManager, UserProfile
from agent.react_agent import ReactAgent
from agent.prompts import PLANNER_PROMPT

def render_main_app():
    # 通过 st.session_state 获取 profile_mgr 实例
    profile_mgr = st.session_state.get('profile_mgr')
    if profile_mgr is None:
        profile_mgr = ProfileManager()
        st.session_state['profile_mgr'] = profile_mgr

    st.title("日本留学智能客服")
    
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

    if "first_run" not in st.session_state:
        with st.chat_message("assistant"):
            st.markdown(f"""
            ### 🌸 欢迎回来，{st.session_state.auth_user.email}！
            我是你的 **留日智能规划专家**。我已经同步了你的云端画像。
            
            **目前我可以为你做：**
            1. **时间线规划**：根据你的 JLPT 进度倒推考学节点。
            2. **名校匹配**：基于 {st.session_state.user_profile.target_major} 数据库匹配教授（2024-2025最新数据）。
            3. **背景诊断**：点击侧边栏更新你的 GPA，我会立刻重新评估你的胜率。
            
            你想从哪个部分开始？
            """)
        st.session_state.first_run = True

    # --- 2. 侧边栏表单 ---
    with st.sidebar:

        st.header("🎓 留学生背景评估")
        
        # 始终从 session_state 获取当前最新的画像（无论是云端的还是刚填好的）
        current_p = st.session_state.user_profile
        
        with st.form("user_profile_form"):
            # 使用 current_p 的属性作为默认值
            jlpt_options = ["无", "N5", "N4", "N3", "N2", "N1"]
            jlpt = st.selectbox("JLPT等级", jlpt_options, index=jlpt_options.index(current_p.jlpt_level))
            
            eju = st.number_input("EJU总分预估", 0, 800, value=int(current_p.eju_score))
            gpa = st.number_input("本科GPA", 0.0, 4.0, value=float(current_p.gpa), step=0.1)
            
            major = st.text_input("意向专业", value=current_p.target_major)
            school = st.text_input("本科院校", value=current_p.undergraduate_school)
            eng_score = st.text_input("英语成绩 (托福/托业/雅思)", value=current_p.english_score)
            
            submitted = st.form_submit_button("更新并保存画像")
            
            if submitted:
                # 构造新的 Profile 对象
                updated_profile = UserProfile(
                    jlpt_level=jlpt,
                    eju_score=eju,
                    gpa=gpa,
                    target_major=major,
                    undergraduate_school=school,
                    english_score=eng_score
                )
                
                # 同步到数据库
                profile_mgr.save_profile(current_user_id, updated_profile)
                
                # 更新 Session 状态，确保 Agent 调用时拿到的是最新的
                st.session_state.user_profile = updated_profile
                
                st.success("✅ 画像已同步至云端！")
                st.rerun() # 立即触发重绘，让 Agent 逻辑感知到新画像
        # ... 放入你之前的 st.sidebar 表单代码 ...
        # ... 包括 submitted 后的 profile_mgr.save_profile 逻辑 ...

    # --- 3. Agent 对话逻辑 ---
    # ... 放入你之前的 Agent 调用、Decision 判定、Execute Stream 代码 ...
    def get_agent():
        profile_dict = {
            "jlpt_level": st.session_state.user_profile.jlpt_level,
            "eju_score": st.session_state.user_profile.eju_score,
            "gpa": st.session_state.user_profile.gpa,
            "target_major": st.session_state.user_profile.target_major,
            "undergraduate_school": st.session_state.user_profile.undergraduate_school,
            "english_score": st.session_state.user_profile.english_score
        }
        return ReactAgent(user_profile=profile_dict)
    if "agent" not in st.session_state or submitted:
        st.session_state["agent"] = get_agent()
        if submitted:
            st.sidebar.success("Agent 已同步最新背景！")
        
    # --- 3. Agent 调用逻辑 ---
    if "agent" not in st.session_state:
        st.session_state["agent"] = ReactAgent()

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # 显示历史消息
    for message in st.session_state["messages"]:
        st.chat_message(message["role"]).write(message["content"])

    prompt = st.chat_input()

    if prompt:
        st.chat_message("user").write(prompt)
        st.session_state["messages"].append({"role": "user", "content": prompt})

        # 1. 把 Pydantic 对象转成 Agent 易读的字符串
        profile_string = profile_mgr.format_for_prompt(st.session_state.user_profile)
        # print(f"\n[DEBUG 1 - App] 即将发送的画像内容:\n{profile_string[:100]}...") # 临时打印，用于调试
        
        response_messages = []

        with st.status("💡 正在规划最佳路径...", expanded=False) as status:
            # 调用一个简单的 chat 接口做决策
            decision = st.session_state["agent"].make_decision(
                PLANNER_PROMPT,
                profile_string,
                prompt
            )
            st.write(f"决策引擎输出: {decision}")

            # 根据决策动态调整状态
            if "[MISSING_INFO]" in decision:
                st.warning("检测到关键背景缺失，建议完善侧边栏信息以获得更精准的建议。")
            elif "[MISSING_INFO]" in decision:
                st.toast("提示：完善侧边栏背景可以让建议更准哦！")

            status.update(label="规划完成", state="complete")

        try:
            with st.spinner("日本留学智能助手思考中..."): 
                # 获取流
                # 2. 这里的第二个参数传字符串 profile_string
                res_stream = st.session_state["agent"].execute_stream(prompt, profile_string)

                def capture(generator, cache_list):
                    try:
                        for chunk in generator:
                            cache_list.append(chunk)
                            yield chunk
                    except Exception as e:
                        # 捕获生成器内部的错误（比如 Tool 运行报错）
                        yield f"\n\n**系统提示**：抱歉，处理过程中遇到了点小麻烦 ({str(e)})。但我会尝试根据已有信息为您回答。"

                with st.chat_message("assistant"):
                    st.write_stream(capture(res_stream, response_messages))

            if response_messages:                   
                st.session_state["messages"].append({"role": "assistant", "content": "".join(response_messages)})

                st.rerun()
        except Exception as e:
            st.error(f"Agent 启动失败：{str(e)}")
            st.stop()