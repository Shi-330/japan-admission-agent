import os
from pathlib import Path
import sys

# 基础配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DASHSCOPE_API_KEY
os.environ["DASHSCOPE_API_KEY"] = DASHSCOPE_API_KEY

import streamlit as st
from agent.react_agent import ReactAgent


st.title("智扫通机器人智能客服")
st.divider()    # 分隔符


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