import streamlit as st
from agent.react_agent import ReactAgent


st.title("日本留学智能客服")
st.divider()    # 分隔符

# app.py 增加部分
with st.sidebar:
    st.header("🎓 留学生背景评估")
    with st.form("user_profile"):
        jlpt = st.selectbox("JLPT等级", ["无", "N5", "N4", "N3", "N2", "N1"])
        eju = st.number_input("EJU总分预估", 0, 800, 0)
        gpa = st.number_input("本科GPA", 0.0, 4.0, 3.0, step=0.1)
        major = st.text_input("意向专业", placeholder="例如：计算机、经营学")
        
        submitted = st.form_submit_button("更新画像")
        if submitted:
            st.session_state.user_profile = {
                "jlpt": jlpt,
                "eju": eju,
                "gpa": gpa,
                "major": major
            }
            st.success("画像已更新，AI 咨询师已就绪！")

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