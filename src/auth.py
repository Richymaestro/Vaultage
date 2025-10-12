# src/auth.py
import os
import streamlit as st

PASSWORD_ENV = "APP_PASSWORD"

def _is_protected() -> bool:
    """Auth is enabled only if APP_PASSWORD is set and non-empty."""
    pw = os.getenv(PASSWORD_ENV, "")
    return bool(str(pw).strip())

def is_authed() -> bool:
    """True if either auth disabled OR session has authed=True."""
    if not _is_protected():
        return True
    return bool(st.session_state.get("authed", False))

def check_password(pw_input: str) -> bool:
    """Compare against APP_PASSWORD from .env/env."""
    pw = os.getenv(PASSWORD_ENV, "")
    return bool(pw) and (str(pw_input) == str(pw))

def require_login_on_home():
    """
    Call this at the TOP of streamlit_app.py (after set_page_config ok too).
    If not authed, RENDER an inline login form here and stop the script.
    This prevents any page-switch loops.
    """
    if is_authed():
        return

    st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: linear-gradient(180deg,#0b1020 0%,#0e1426 100%); color:#e6e9ef; }
.login-card { background:#0e1a36; border:1px solid #233257; border-radius:16px; padding:24px; max-width:420px; margin:10vh auto; }
.login-card h2 { margin:0 0 12px; }
</style>
""", unsafe_allow_html=True)

    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.header("Sign in")
    with st.form("login"):
        pw = st.text_input("Password", type="password", help="Set APP_PASSWORD in your environment (.env).")
        submitted = st.form_submit_button("Log in", use_container_width=True)
        if submitted:
            if check_password(pw):
                st.session_state["authed"] = True
                st.success("Welcome!")
                st.rerun()
            else:
                st.error("Invalid password.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

def guard_other_pages():
    """
    Use this at the top of pages/* (Vault, Reallocations, Comparisons).
    If not authed, DO NOT redirect. Just show a small notice linking back home and stop.
    This avoids ping-pong loops.
    """
    if is_authed():
        return
    st.warning("🔒 Please log in on the homepage first.")
    st.markdown('[Go to homepage →](?)')
    st.stop()

def logout_button():
    """Place this in the sidebar. Clears session and reloads home."""
    if st.sidebar.button("Log out", use_container_width=True):
        for k in ("authed",):
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()