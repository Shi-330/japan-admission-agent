# --- app.py ---
import os
# Kill broken system proxy before any module does HTTP
for _v in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_v, None)
os.environ["NO_PROXY"] = "*"
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"  # BGE model download for China

import streamlit as st
from user.profile_manager import profile_mgr
from views.auth_pages import render_auth_page, render_password_reset_page 
from views.main_agent import render_main_app
from views.simple_agent import render_simple_agent

# 1. 初始化 Session State
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None
if "is_resetting" not in st.session_state:
    st.session_state.is_resetting = False
if "agent_mode" not in st.session_state:
    st.session_state.agent_mode = "simple"  # default to new version

# 尝试从 Cookie 恢复会话 (解决刷新掉登录的问题)
try:
    import extra_streamlit_components as stx
    cookie_manager = stx.CookieManager()
    
    # extra_streamlit_components 的 get 需要在 render 后才能获取到，
    # 所以通常我们会依赖它在页面顶部调用来初始化
    access_token = cookie_manager.get(cookie="sb_access_token")
    refresh_token = cookie_manager.get(cookie="sb_refresh_token")
    
    if not st.session_state.auth_user and access_token and refresh_token:
        try:
            res = profile_mgr.supabase.auth.set_session(access_token, refresh_token)
            st.session_state.auth_user = res.user
        except Exception as e:
            # Token 可能过期或网络问题，静默回退到登录页
            from utils.logger_handler import logger
            logger.warning(f"Cookie 会话恢复失败: {e}")
except ImportError:
    pass

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
    # 模式切换
    with st.sidebar:
        st.divider()
        st.session_state.agent_mode = st.radio(
            "Agent 模式",
            ["simple", "react"],
            format_func=lambda x: "简化版 (推荐)" if x == "simple" else "ReAct (旧版)",
            index=0 if st.session_state.agent_mode == "simple" else 1,
        )

    if st.session_state.agent_mode == "simple":
        render_simple_agent()
    else:
        render_main_app()