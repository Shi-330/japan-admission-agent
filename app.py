import streamlit as st
import dotenv
dotenv.load_dotenv()

# 注意这里的顺序：先导入 profile_mgr，再导入依赖它的 views
from user.profile_manager import profile_mgr, UserProfile
from views.auth_pages import render_auth_page, render_password_reset_page 
from views.main_agent import render_main_app 

# 1. 初始化 Session State (将导入的实例存入 session_state)
if 'profile_mgr' not in st.session_state:
    st.session_state['profile_mgr'] = profile_mgr

if "auth_user" not in st.session_state:
    st.session_state.auth_user = None
if "is_resetting" not in st.session_state:
    st.session_state.is_resetting = False

# --- 2. 核心：处理 URL 回调 (OTP 验证) ---
query_params = st.query_params
if "code" in query_params:
    try:
        # 使用导入的 profile_mgr
        res = profile_mgr.supabase.auth.verify_otp({
            "token_hash": query_params["code"],
            "type": "recovery"
        })
        if res.session:
            st.session_state.recovery_access_token = res.session.access_token
            st.session_state.recovery_refresh_token = res.session.refresh_token
            st.session_state.auth_user = res.user
            st.session_state.is_resetting = True
            
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"验证失败: {e}")

# 3. 【防丢补丁】强制挂载 Session
if st.session_state.get("is_resetting") and "recovery_access_token" in st.session_state:
    profile_mgr.supabase.auth.set_session(
        st.session_state.recovery_access_token,
        st.session_state.recovery_refresh_token
    )

# --- 4. 路由拦截逻辑 ---
if st.session_state.is_resetting and st.session_state.auth_user:
    render_password_reset_page()
elif st.session_state.auth_user is None:
    render_auth_page()
    st.stop()
else:
    render_main_app()