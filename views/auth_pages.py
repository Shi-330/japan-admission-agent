import streamlit as st
from user.profile_manager import profile_mgr # 直接导入实例
from supabase import AuthApiError

def render_auth_page():
    st.title("日本留学智能客服")
    st.subheader("欢迎回来")
    
    tab1, tab2, tab3 = st.tabs(["登录", "注册", "忘记密码"])

    with tab1:
        email = st.text_input("邮箱", key="login_email")
        password = st.text_input("密码", type="password", key="login_password")
        if st.button("进入系统", use_container_width=True):
            try:
                res = profile_mgr.supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.auth_user = res.user
                
                # 写入 Cookie 以防刷新掉登录态
                try:
                    import extra_streamlit_components as stx
                    cookie_manager = stx.CookieManager()
                    cookie_manager.set("sb_access_token", res.session.access_token)
                    cookie_manager.set("sb_refresh_token", res.session.refresh_token)
                except Exception:
                    pass
                    
                st.success("登录成功！")
                st.rerun()
            except AuthApiError as e:
                if "invalid" in str(e).lower() or "credentials" in str(e).lower():
                    st.error("登录失败: 用户名或密码错误，请检查后重试。")
                elif "network error" in str(e).lower():
                    st.error("网络连接错误，请检查网络后重试。")
                elif "timeout" in str(e).lower():
                    st.error("连接超时，请稍后重试。")
                else:
                    st.error(f"登录失败: {e}")
            except Exception as general_e:
                st.error(f"登录遇到未知错误: {general_e}")

    with tab2:
        new_email = st.text_input("注册邮箱", key="reg_email")
        new_password = st.text_input("设置密码", type="password", key="reg_password")
        if st.button("提交注册", use_container_width=True):
            try:
                profile_mgr.supabase.auth.sign_up({"email": new_email, "password": new_password})
                st.info("注册成功，请查收邮件确认后登录。")
            except AuthApiError as e:
                if "email" in str(e).lower() and "taken" in str(e).lower():
                    st.error("该邮箱已被注册，请尝试其他邮箱或直接登录。")
                elif "network error" in str(e).lower():
                    st.error("网络连接错误，请检查网络后重试。")
                elif "timeout" in str(e).lower():
                    st.error("连接超时，请稍后重试。")
                else:
                    st.error(f"注册失败: {e}")
            except Exception as general_e:
                st.error(f"注册遇到未知错误: {general_e}")
    
    with tab3:
        st.markdown("### 🔑 重置密码")
        reset_email = st.text_input("请输入注册邮箱", key="reset_pwd_email")
        # 登录页的"忘记密码"逻辑片段
        if st.button("忘记密码？"):
            if reset_email:
                try:
                    profile_mgr.supabase.auth.reset_password_for_email(reset_email)
                    st.session_state.temp_reset_email = reset_email
                    st.session_state.is_resetting = True
                    st.rerun()
                except AuthApiError as e:
                    if "rate limit" in str(e).lower():
                        st.error("邮件发送过于频繁，请稍后再试。")
                    elif "email" in str(e).lower() and "not found" in str(e).lower():
                        st.error("该邮箱未注册，请检查后重试。")
                    else:
                        st.error(f"发送失败: {e}")
                except Exception as general_e:
                    st.error(f"请求重置密码时遇到未知错误: {general_e}")
            else:
                st.warning("请先在邮箱栏输入您的账号")

def render_password_reset_page():
    st.title("🔒 重置密码")
    st.info("请检查您的邮箱获取 6 位验证码")

    # 这里的 email 可以从 session_state 拿，或者让用户再输一遍
    # 建议在跳转到这个页面前，把用户输入的 email 存下来
    email = st.session_state.get("temp_reset_email", "")
    
    with st.form("otp_reset_form"):
        target_email = st.text_input("确认邮箱", value=email)
        otp_code = st.text_input("6 位验证码", max_chars=6)
        new_password = st.text_input("设置新密码", type="password", help="至少 6 位")
        confirm_password = st.text_input("确认新密码", type="password")
        
        submit = st.form_submit_button("提交修改", type="primary") 
        
        if submit:
            if new_password != confirm_password:
                st.error("两次密码不一致")
            elif len(new_password) < 6:
                st.error("密码太短啦，至少要 6 位哦")
            else:
                try:
                    # 1. 先验证验证码是否正确
                    res = profile_mgr.supabase.auth.verify_otp({
                        "email": target_email,
                        "token": otp_code,
                        "type": "recovery" # 对应重置密码类型
                    })
                    
                    if res.session:
                        # 2. 验证码通过后，res.session 会自动把当前会话设为已认证
                        # 此时直接更新密码
                        profile_mgr.supabase.auth.update_user({"password": new_password})
                        st.success("🎉 密码修改成功！")
                        # 修改完后，把状态重置，让用户重新登录
                        st.session_state.is_resetting = False
                        st.session_state.auth_user = None
                        st.balloons()
                        st.info("请使用新密码重新登录")
                        st.rerun()
                except AuthApiError as e:
                    st.error(f"修改失败：验证码可能错误或已过期。({e})")
                except Exception as general_e:
                    st.error(f"修改密码时遇到未知错误: {general_e}")

    if st.button("返回登录"):
        st.session_state.is_resetting = False
        st.rerun()