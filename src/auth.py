# src/auth.py
import streamlit as st
import os

def is_localhost() -> bool:
    """Detect if the app is running locally."""
    # Works for 'streamlit run' on localhost
    host = os.getenv("STREAMLIT_SERVER_ADDRESS", "")
    return host in ("localhost", "127.0.0.1", "")

def require_login():
    """Simple login page that only shows up in non-local environments."""
    if is_localhost():
        return True  # bypass login locally

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        return True

    st.title("🔒 Login Required")
    st.markdown("Please enter your credentials to access the dashboard.")

    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")

    if st.button("Login"):
        # You can replace this with your actual auth logic
        if user == os.getenv("APP_USER") and pw == os.getenv("APP_PASS"):
            st.session_state.logged_in = True
            st.experimental_rerun()
        else:
            st.error("Invalid credentials")

    st.stop()  # block the rest of the app