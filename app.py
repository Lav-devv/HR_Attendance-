import os
import json
import zipfile
import importlib
import inspect
import calendar
from datetime import date, datetime
import pandas as pd
import streamlit as st
import rules

importlib.reload(rules)

from parser import parse_chat
from report import generate_shareable_report, generate_monthly_shareable_report
import auth

importlib.reload(auth)

LOGO_PATH = "logo.png"
REVIEWED_FILE = "reviewed_overrides.json"

st.set_page_config(
    page_title="TechNaka Attendance Analyzer",
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

if os.path.exists(LOGO_PATH):
    st.logo(LOGO_PATH, size="large")


def _safe_register(username, password, role="viewer", employee_name=""):
    fn = getattr(auth, "register_user")
    try:
        return fn(username, password, role=role, employee_name=employee_name)
    except TypeError:
        return fn(username, password)


def _safe_authenticate(username, password):
    fn = getattr(auth, "authenticate_user")
    result = fn(username, password)
    if isinstance(result, tuple) and len(result) == 2:
        ok, info = result
        if isinstance(info, dict):
            return ok, info
        if ok:
            return True, {"username": str(username).strip().lower(), "role": "admin", "employee_name": ""}
    if result is True:
        return True, {"username": str(username).strip().lower(), "role": "admin", "employee_name": ""}
    return False, None


def _safe_reset_password(username, verification_input, new_password):
    fn = getattr(auth, "reset_password", None)
    if callable(fn):
        return fn(username, verification_input, new_password)
    return False, "Password reset is not available in auth.py."


def _safe_workspace(username):
    fn = getattr(auth, "get_user_workspace")
    return fn(username)


def _safe_delete_data(username):
    fn = getattr(auth, "delete_user_data")
    return fn(username)


def load_reviewed_map(workspace_dir: str) -> dict:
    path = os.path.join(workspace_dir, REVIEWED_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def save_reviewed_map(workspace_dir: str, data: dict) -> None:
    os.makedirs(workspace_dir, exist_ok=True)
    path = os.path.join(workspace_dir, REVIEWED_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def filter_df_for_viewer(df: pd.DataFrame, username: str, employee_name: str) -> pd.DataFrame:
    if df.empty or "Employee" not in df.columns:
        return df.iloc[0:0].copy()

    targets = [t.strip().lower() for t in [employee_name, username] if t and t.strip()]
    if not targets:
        return df.iloc[0:0].copy()

    emp_series = df["Employee"].astype(str).str.strip().str.lower()
    mask = emp_series.isin(targets) | emp_series.apply(lambda x: any(t in x for t in targets))
    return df[mask].copy()


# --- CUSTOM DARK FOREST UI STYLING ---
st.markdown(
    """
<style>
    .stApp {
        background: radial-gradient(circle at top left, #0E2923 0%, #071714 65%);
        color: #EAF4F1;
    }
    section[data-testid="stSidebar"] {
        background-color: #091D19;
        border-right: 1px solid #173B33;
    }
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
    }
    .kpi-card {
        background: #0B211C;
        border: 1.5px solid #1C473D;
        border-radius: 14px;
        padding: 14px 16px;
        min-height: 105px;
    }
    .kpi-green {
        border-color: #2E7D32;
    }
    .kpi-gold {
        border-color: #C99A2E;
    }
    .kpi-title {
        font-size: 0.85rem;
        color: #B7CEC8;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        color: #FFFFFF;
        line-height: 1.1;
    }
    .cal-box {
        background: #0A1F1A;
        border: 1.5px solid #1B4239;
        border-radius: 14px;
        padding: 12px 14px;
        font-size: 0.78rem;
    }
    .user-meta {
        text-align: right;
        font-size: 0.82rem;
        color: #9EB8B1;
        margin-top: 4px;
    }
    .role-badge-admin {
        display: inline-block;
        background: #1B4332;
        color: #95D5B2;
        border: 1px solid #40916C;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .role-badge-viewer {
        display: inline-block;
        background: #1E293B;
        color: #CBD5E1;
        border: 1px solid #475569;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    div.stDownloadButton > button {
        background-color: #FFFFFF !important;
        color: #081A16 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: none !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = "viewer"
if "employee_name" not in st.session_state:
    st.session_state.employee_name = ""


def render_calendar_widget(focus_date: date):
    cal = calendar.Calendar(firstweekday=6)
    month_days = cal.monthdayscalendar(focus_date.year, focus_date.month)
    month_label = focus_date.strftime("%b %d, %Y")

    rows_html = ""
    for week in month_days:
        cells = ""
        for day_num in week:
            if day_num == 0:
                cells += "<td style='padding:3px;color:#3B5B53;text-align:center;'>·</td>"
            elif day_num == focus_date.day:
                cells += (
                    f"<td style='padding:3px;background:#2E7D32;color:#FFFFFF;"
                    f"border-radius:5px;font-weight:700;text-align:center;'>{day_num}</td>"
                )
            else:
                cells += f"<td style='padding:3px;color:#D4E6E1;text-align:center;'>{day_num}</td>"
        rows_html += f"<tr>{cells}</tr>"

    st.markdown(
        f"""
    <div class="cal-box">
        <div style="display:flex;justify-content:space-between;font-weight:600;margin-bottom:6px;">
            <span>&lt;</span>
            <span>{month_label}</span>
            <span>&gt;</span>
        </div>
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr style="color:#85A39B;">
                    <th>Su</th><th>Mo</th><th>Tu</th><th>We</th><th>Th</th><th>Fr</th><th>Sa</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """,
        unsafe_allow_html=True,
    )


# --- LOGIN / REGISTER / FORGOT PASSWORD GATE ---
if not st.session_state.authenticated or not st.session_state.username:
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        with st.container(border=True):
            if os.path.exists(LOGO_PATH):
                st.image(LOGO_PATH, width=140)
            else:
                st.warning("Place logo.png in the project folder to display the TechNaka logo.")
            st.markdown("### TechNaka Attendance Analyzer")
            st.caption("Registered accounts remain saved permanently; admins manage attendance reviews.")

        tab_login, tab_register, tab_forgot = st.tabs(["Login", "Create Account", "Forgot Password"])

        with tab_login:
            with st.form("login_form"):
                login_user = st.text_input("Username")
                login_pass = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    ok, user_info = _safe_authenticate(login_user, login_pass)
                    if ok and user_info:
                        st.session_state.authenticated = True
                        st.session_state.username = user_info["username"]
                        st.session_state.role = user_info["role"]
                        st.session_state.employee_name = user_info["employee_name"]
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

        with tab_register:
            with st.form("register_form"):
                new_user = st
