# src/auth.py
import os
import hashlib
import streamlit as st

def _bypass_enabled() -> bool:
    # Disable auth if env or secrets explicitly say so (use in local dev)
    raw = str(st.secrets.get("disable_auth", os.getenv("DISABLE_AUTH", "0")))
    return raw.strip().lower() in ("1", "true", "yes", "on")

def _check_user_pass(user: str, pw: str) -> bool:
    # Prefer secrets: [auth] users = { username = "password_or_sha256$hex" }
    users = st.secrets.get("auth", {}).get("users", {})
    if users:
        if user in users:
            stored = str(users[user])
            # allow SHA256: "sha256$<hex>"
            if stored.startswith("sha256$"):
                h = hashlib.sha256(pw.encode()).hexdigest()
                return h == stored.split("$", 1)[1]
            return pw == stored
        return False

    # Fallback env (single user)
    eu = os.getenv("APP_USER")
    ep = os.getenv("APP_PASS")
    if eu and ep:
        return user == eu and pw == ep

    # No configured credentials -> lock down by default
    return False

def _check_token(tok: str) -> bool:
    # Optional magic link token (?token=...)
    t_secret = st.secrets.get("auth", {}).get("token") or os.getenv("AUTH_TOKEN")
    return bool(t_secret) and tok == str(t_secret)

def require_login() -> bool:
    """
    Gate the page. Returns True if access is granted; otherwise renders a login form and stops.
    Auth is enabled by default unless disabled via DISABLE_AUTH=1 or secrets.disable_auth=true.
    """
    # Bypass explicitly for local/dev
    if _bypass_enabled():
        st.session_state.logged_in = True
        st.session_state.username = "local"
        return True

    # One-time token via URL (?token=...)
    qp = st.query_params
    tok = qp.get("token")
    if tok and _check_token(tok if isinstance(tok, str) else str(tok)):
        st.session_state.logged_in = True
        st.session_state.username = "token"
        return True

    # Session already authenticated
    if st.session_state.get("logged_in"):
        return True

    # Render login form and block page
    st.markdown("## 🔒 Login")
    with st.form("login_form", clear_on_submit=False):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        ok = st.form_submit_button("Sign in")

    if ok:
        if _check_user_pass(u, p):
            st.session_state.logged_in = True
            st.session_state.username = u
            st.experimental_rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

def logout_button():
    if st.sidebar.button("Log out"):
        for k in ("logged_in", "username"):
            st.session_state.pop(k, None)
        st.experimental_rerun()