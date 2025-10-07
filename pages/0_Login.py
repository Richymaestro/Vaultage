# pages/0_Login.py
import streamlit as st
from src.auth import check_password, is_authed

st.set_page_config(page_title="Login", layout="centered")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: linear-gradient(180deg,#0b1020 0%,#0e1426 100%); color:#e6e9ef; }
.login-card { background:#0e1a36; border:1px solid #233257; border-radius:16px; padding:24px; max-width:420px; margin:10vh auto; }
.login-card h2 { margin:0 0 12px; }
</style>
""", unsafe_allow_html=True)

if is_authed():
    st.success("You're already logged in.")
    st.page_link("streamlit_app.py", label="→ Go to Dashboard", use_container_width=True)
    st.stop()

st.markdown('<div class="login-card">', unsafe_allow_html=True)
st.header("Sign in")
with st.form("login"):
    pw = st.text_input("Password", type="password", help="Set APP_PASSWORD in your environment to enable auth.")
    submitted = st.form_submit_button("Log in", use_container_width=True)
    if submitted:
        if check_password(pw):
            st.session_state["authed"] = True
            st.success("Welcome!")
            st.page_link("streamlit_app.py", label="→ Continue to Dashboard", use_container_width=True)
            st.stop()
        else:
            st.error("Invalid password.")
st.markdown('</div>', unsafe_allow_html=True)