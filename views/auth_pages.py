import streamlit as st
from user.profile_manager import profile_mgr # 直接导入实例

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
                st.success("登录成功！")
                st.rerun()
            except Exception as e:
                st.error(f"登录失败: {e}")

    with tab2:
        new_email = st.text_input("注册邮箱", key="reg_email")
        new_password = st.text_input("设置密码", type="password", key="reg_password")
        if st.button("提交注册", use_container_width=True):
            try:
                profile_mgr.supabase.auth.sign_up({"email": new_email, "password": new_password})
                st.info("注册成功，请查收邮件确认后登录。")
            except Exception as e:
                st.error(f"注册失败: {e}")
    
    with tab3:
        st.markdown("### 🔑 重置密码")
        reset_email = st.text_input("请输入注册邮箱", key="reset_pwd_email")
        if st.button("发送重置邮件", use_container_width=True):
            try:
                # 生产环境逻辑
                profile_mgr.send_reset_password_email(reset_email)
                st.success("✅ 邮件已发送！请通过邮件链接跳转回来。")
            except Exception as e:
                st.error(f"发送失败: {e}")

def render_password_reset_page():
    """
    专门处理密码重置页面的函数
    """
    st.title("🔒 设置您的新密码")
    st.info(f"正在重置账户：{st.session_state.auth_user.email}")

    # 这里的 auth_user 是在 app.py 里的 verify_otp 步骤存入 session_state 的
    if st.session_state.get("auth_user"):
        st.info(f"正在重置账户：{st.session_state.auth_user.email}")
    
    with st.form("reset_password_final"):
        new_pwd = st.text_input("新密码", type="password", help="至少6位")
        confirm_pwd = st.text_input("确认新密码", type="password")
        btn = st.form_submit_button("保存新密码并进入系统", use_container_width=True)
        
        if btn:
            if new_pwd == confirm_pwd and len(new_pwd) >= 6:
                try:
                    # 使用 update_user 更新密码，此时 session 已经在顶部 exchange 好了
                    profile_mgr.supabase.auth.update_user({"password": new_pwd})
                    st.success("✅ 密码修改成功！")
                    st.session_state.is_resetting = False
                    st.rerun()
                except Exception as e:
                    st.error(f"更新失败: {e}")
            else:
                st.error("⚠️ 密码不匹配或过短")

    if st.button("取消重置"):
        st.session_state.is_resetting = False
        st.session_state.clear()
        st.rerun()
    st.stop()