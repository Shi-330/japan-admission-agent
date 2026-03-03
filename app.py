# --- app.py ---
import streamlit as st
from user.profile_manager import profile_mgr
from views.auth_pages import render_auth_page, render_password_reset_page 
from views.main_agent import render_main_app 

# 1. 初始化 Session State
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None
if "is_resetting" not in st.session_state:
    st.session_state.is_resetting = False

# --- 2. 路由分流 (现在逻辑非常纯粹) ---

if st.session_state.is_resetting:
    # 只要这个标志位为 True，就显示重置页面
    render_password_reset_page()
    st.stop()

elif st.session_state.auth_user is None:
    # 没登录就显示登录/注册页
    render_auth_page()
    st.stop()

else:
    # 正常登录状态显示主应用
    render_main_app()