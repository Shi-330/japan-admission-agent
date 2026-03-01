import streamlit as st
from agent.react_agent import ReactAgent
import dotenv
dotenv.load_dotenv()
from user.profile_manager import ProfileManager, UserProfile

st.title("日本留学智能客服")
st.divider()

# --- 1. 初始化 ---
profile_mgr = ProfileManager()
# 这里你可以暂时固定一个 UUID 进行测试，未来可以改为用户登录后的 ID
user_id = "00000000-0000-0000-0000-000000000001" 

# --- 2. 核心加载逻辑 ---
# 如果 Session 没内容，get_profile 会自动从线上数据库取数据
if "user_profile" not in st.session_state:
    with st.spinner("正在同步云端画像..."):
        # 如果数据库有内容，saved_profile 就是数据库里的；没有则是默认值
        saved_profile = profile_mgr.get_profile(user_id)
        st.session_state.user_profile = saved_profile

with st.sidebar:
    st.header("🎓 留学生背景评估")
    
    current_p = st.session_state.user_profile
    
    with st.form("user_profile_form"):
        jlpt_options = ["无", "N5", "N4", "N3", "N2", "N1"]
        jlpt = st.selectbox("JLPT等级", jlpt_options, index=jlpt_options.index(current_p.jlpt_level))
        
        eju = st.number_input("EJU总分预估", 0, 800, int(current_p.eju_score))
        gpa = st.number_input("本科GPA", 0.0, 4.0, float(current_p.gpa), step=0.1)
        
        major = st.text_input("意向专业", value=current_p.target_major)
        school = st.text_input("本科院校", value=current_p.undergraduate_school)
        
        # --- 补全英语成绩 ---
        eng_score = st.text_input("英语成绩 (托福/托业/雅思)", value=current_p.english_score)
        
        submitted = st.form_submit_button("更新并保存画像")
        
        if submitted:
            new_profile = UserProfile(
                jlpt_level=jlpt,
                eju_score=eju,
                gpa=gpa,
                target_major=major,
                undergraduate_school=school,
                english_score=eng_score # 保存新字段
            )
            profile_mgr.save_profile(user_id, new_profile)
            st.session_state.user_profile = new_profile
            st.success("✅ 画像已同步至云端数据库！")
            st.rerun()

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

    response_messages = []
    with st.spinner("智能客服思考中..."): 
        # 2. 这里的第二个参数传字符串 profile_string
        res_stream = st.session_state["agent"].execute_stream(prompt, profile_string)

        def capture(generator, cache_list):
            for chunk in generator:
                cache_list.append(chunk)
                yield chunk
        
        st.chat_message("assistant").write_stream(capture(res_stream, response_messages))
        st.session_state["messages"].append({"role": "assistant", "content": response_messages[-1]})

        st.rerun()