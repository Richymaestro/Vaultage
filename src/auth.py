# src/auth.py
import os
import hashlib
import streamlit as st

try:
    # optional: load .env automatically if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ---------------------------
# ENV KEYS (all optional)
# ---------------------------
# DISABLE_AUTH=1                     -> bypass login (handy for local dev)
# APP_USER=admin                     -> username
# APP_PASS=supersecret               -> password (plain), OR:
# APP_PASS=sha256$<hex>              -> password as SHA256 hash
# AUTH_TOKEN=some-long-token         -> enables magic link: ?token=some-long-token

def _bypass_enabled() -> bool:
    raw = os.getenv("DISABLE_AUTH", "0")
    return str(raw).strip().lower() in ("1", "true", "yes", "on")

def _check_user_pass(user: str, pw: str) -> bool:
    eu = os.getenv("APP_USER")
    ep = os.getenv("APP_PASS")
    if not eu or not ep:
        # No creds configured -> lock down by default unless auth bypassed
        return False

    if user != eu:
        return False

    stored = str(ep)
    if stored.startswith("sha256$"):
        h = hashlib.sha256(pw.encode()).hexdigest()
        return h == stored.split("$", 1)[1]
    return pw == stored

def _check_token(tok: str) -> bool:
    t = os.getenv("AUTH_TOKEN", "")
    return bool(t) and tok == t

# ---------------------------
# Entry-page gate (shows form ONCE)
# ---------------------------
def require_login_on_home() -> bool:
    """
    Call this ONLY in streamlit_app.py (home).
    Auth is ON by default. Locally you can set DISABLE_AUTH=1 to bypass.
    """
    if _bypass_enabled():
        st.session_state.logged_in = True
        st.session_state.username = "local"
        return True

    # Magic link via ?token=...
    qp = st.query_params
    tok = qp.get("token")
    if isinstance(tok, list):  # older streamlit might return list
        tok = tok[0] if tok else None
    if tok and _check_token(str(tok)):
        st.session_state.logged_in = True
        st.session_state.username = "token"
        return True

    if st.session_state.get("logged_in"):
        return True

    st.markdown("## 🔒 Login")
    with st.form("login_form", clear_on_submit=False):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        ok = st.form_submit_button("Sign in")

    if ok:
        if _check_user_pass(u, p):
            st.session_state.logged_in = True
            st.session_state.username = u
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

# ---------------------------
# Other pages (no form)
# ---------------------------
def guard_other_pages():
    """
    Call this at the top of every subpage (pages/*.py).
    If not logged in, show a link back to home and stop.
    """
    if _bypass_enabled():
        return True
    if st.session_state.get("logged_in"):
        return True

    st.markdown("### 🔒 Please log in")
    st.info("Sign in on the homepage first.")
    st.markdown('<a class="sidebar-link" href="?">Go to Login</a>', unsafe_allow_html=True)
    st.stop()

# ---------------------------
# Logout button (optional)
# ---------------------------
def logout_button():
    if st.sidebar.button("Log out"):
        for k in ("logged_in", "username"):
            st.session_state.pop(k, None)
        st.rerun()