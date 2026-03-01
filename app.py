import streamlit as st
from agent.react_agent import ReactAgent
import dotenv
dotenv.load_dotenv()
# --- 新增：导入你的管理类 ---
from user.profile_manager import ProfileManager, UserProfile


st.title("日本留学智能客服")
st.divider()

# --- 1. 初始化 ProfileManager ---
# 建议给每个用户一个 ID，目前单机版先写死 "default_user"
profile_mgr = ProfileManager()
# 修改前：user_id = "default_user"
# 修改后（找一个标准的 UUID）：
user_id = "00000000-0000-0000-0000-000000000001"

# --- 2. 初始加载：如果 session 中没有，则从 JSON 文件载入 ---
if "user_profile" not in st.session_state:
    # get_profile 会返回一个 UserProfile 对象
    saved_profile = profile_mgr.get_profile(user_id)
    st.session_state.user_profile = saved_profile

with st.sidebar:
    st.header("🎓 留学生背景评估")
    
    # 获取当前的画像数据（用于给输入框赋初值）
    current_p = st.session_state.user_profile
    
    with st.form("user_profile_form"):
        # 使用 saved_profile 的值作为默认值 (index 或 value)
        jlpt_options = ["无", "N5", "N4", "N3", "N2", "N1"]
        jlpt = st.selectbox("JLPT等级", jlpt_options, index=jlpt_options.index(current_p.jlpt_level))
        
        eju = st.number_input("EJU总分预估", 0, 800, int(current_p.eju_score))
        gpa = st.number_input("本科GPA", 0.0, 4.0, float(current_p.gpa), step=0.1)
        
        # 对应 UserProfile 中的 target_major 和 undergraduate_school
        major = st.text_input("意向专业", value=current_p.target_major)
        school = st.text_input("本科院校", value=current_p.undergraduate_school)
        
        submitted = st.form_submit_button("更新并保存画像")
        
        if submitted:
            # --- 3. 提交时：构造 Pydantic 对象并保存到文件 ---
            new_profile = UserProfile(
                jlpt_level=jlpt,
                eju_score=eju,
                gpa=gpa,
                target_major=major,
                undergraduate_school=school
            )
            # 保存到长期存储 (JSON)
            profile_mgr.save_profile(user_id, new_profile)
            # 更新到 Session
            st.session_state.user_profile = new_profile
            
            st.success("画像已同步至数据库！")
            st.rerun() # 强制刷新页面让数据生效

# --- 后续 Agent 调用逻辑保持不变 ---
# (但在初始化 Agent 时，你可以考虑把 st.session_state.user_profile 传进去)
if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for message in st.session_state["messages"]:
    st.chat_message(message["role"]).write(message["content"])

prompt = st.chat_input()

if prompt:
    st.chat_message("user").write(prompt)
    st.session_state["messages"].append({"role": "user", "content": prompt})

    response_messages = []
    with st.spinner("智能客服思考中..."): 
        res_stream = st.session_state["agent"].execute_stream(prompt)

        def capture(generator, cache_list): # 缓存,记录内容

            for chunk in generator:
                cache_list.append(chunk)
                yield chunk
        
        st.chat_message("assistant").write_stream(capture(res_stream, response_messages))
        st.session_state["messages"].append({"role": "assistant", "content": response_messages[-1]})

        # 如果不加这一条的话，会保留一大堆思考过程
        st.rerun()