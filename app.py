import os
import json
import zipfile
import importlib
import inspect
import calendar
from datetime import date
import pandas as pd
import streamlit as st
import rules

importlib.reload(rules)

from parser import parse_chat
from report import generate_shareable_report, generate_monthly_shareable_report
from auth import register_user, authenticate_user, get_user_workspace, delete_user_data

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


# --- CUSTOM DARK FOREST UI STYLING ---
st.markdown("""
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
    div.stDownloadButton > button {
        background-color: #FFFFFF !important;
        color: #081A16 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None


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

    st.markdown(f"""
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
    """, unsafe_allow_html=True)


# --- LOGIN / REGISTER GATE ---
if not st.session_state.authenticated or not st.session_state.username:
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        with st.container(border=True):
            if os.path.exists(LOGO_PATH):
                st.image(LOGO_PATH, width=140)
            else:
                st.warning("Place `logo.png` in the project folder to display the TechNaka logo.")
            st.markdown("### TechNaka Attendance Analyzer")
            st.caption("Private Workspace: Your uploads and employee records are isolated to your account.")

        tab_login, tab_register = st.tabs(["Login", "Create Account"])

        with tab_login:
            with st.form("login_form"):
                login_user = st.text_input("Username")
                login_pass = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    if authenticate_user(login_user, login_pass):
                        st.session_state.authenticated = True
                        st.session_state.username = login_user.strip().lower()
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

        with tab_register:
            with st.form("register_form"):
                new_user = st.text_input("Choose Username (letters & numbers only)")
                new_pass = st.text_input("Choose Password (min 6 chars)", type="password")
                reg_submitted = st.form_submit_button("Register", use_container_width=True)
                if reg_submitted:
                    ok, msg = register_user(new_user, new_pass)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

# --- AUTHENTICATED PRIVATE WORKSPACE ---
else:
    current_user = st.session_state.username
    user_workspace = get_user_workspace(current_user)
    private_emp_path = os.path.join(user_workspace, "employees.csv")
    reviewed_map = load_reviewed_map(user_workspace)

    with st.sidebar:
        st.markdown("### Upload Employees (.csv)")
        emp_upload = st.file_uploader("Upload Employees (.csv)", type=["csv"], key="emp_csv", label_visibility="collapsed")
        if emp_upload is not None:
            with open(private_emp_path, "wb") as f:
                f.write(emp_upload.getbuffer())
            st.success("Saved to private workspace")

        if os.path.exists(private_emp_path):
            st.markdown("<span style='color:#66BB6A;font-size:0.85rem;'>✓ employees.csv active</span>", unsafe_allow_html=True)
        else:
            st.caption("Using names detected from chat")

        st.markdown("---")
        st.markdown("### Upload Attendance (.zip)")
        uploaded_zip = st.file_uploader("Upload Attendance (.zip)", type=["zip"], key="att_zip", label_visibility="collapsed")

        st.markdown("---")
        if st.button("Wipe My Private Data", use_container_width=True):
            delete_user_data(current_user)
            st.success("Private data wiped.")
            st.rerun()

    # --- TOP HEADER BAR WITH LOGO ---
    h_logo, h_title, h_right = st.columns([1.3, 6.2, 2.5])
    with h_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, use_container_width=True)
        else:
            st.caption("logo.png missing")

    with h_title:
        st.markdown(
            "<h1 style='margin:0;font-size:2rem;line-height:1.15;'>TechNaka Attendance Analyzer<br>"
            "<span style='font-size:1.55rem;font-weight:600;'>(Private Workspace)</span></h1>",
            unsafe_allow_html=True,
        )

    with h_right:
        _, btn_col = st.columns([1, 1.3])
        with btn_col:
            if st.button("↪ Logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        st.markdown(f"<div class='user-meta'>Logged in as: <b>{current_user}</b></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    cal_focus_date = date.today()
    attendance_df = pd.DataFrame()
    daily_report = pd.DataFrame()
    selected_date = None

    if uploaded_zip is not None:
        try:
            with zipfile.ZipFile(uploaded_zip, "r") as z:
                all_files = [
                    name for name in z.namelist()
                    if not name.startswith("__MACOSX/") and not name.endswith("/")
                ]
                txt_filenames = [name for name in all_files if name.lower().endswith(".txt")]

                if not txt_filenames:
                    st.error(f"No .txt chat file found inside ZIP. Files detected: {all_files}")
                else:
                    target_txt = next((n for n in txt_filenames if "_chat.txt" in n.lower()), txt_filenames[0])
                    with z.open(target_txt) as f:
                        raw_bytes = f.read()

                    chat_df = parse_chat(raw_bytes)
                    if not chat_df.empty:
                        sig = inspect.signature(rules.apply_attendance_rules)
                        if "workspace_dir" in sig.parameters:
                            attendance_df = rules.apply_attendance_rules(chat_df, workspace_dir=user_workspace)
                        else:
                            attendance_df = rules.apply_attendance_rules(chat_df)

                        if reviewed_map:
                            def _apply_saved_review(row):
                                key = f"{row['Date']}|{str(row['Employee']).strip()}"
                                if key in reviewed_map and row["Status"] == "Pending review":
                                    return "Reviewed"
                                return row["Status"]

                            attendance_df["Status"] = attendance_df.apply(_apply_saved_review, axis=1)
                    else:
                        st.warning("Chat file opened, but no valid messages matched the date/time format.")
        except Exception as e:
            st.error(f"Error reading ZIP file: {e}")

    # --- KPI ROW + MINI CALENDAR ---
    k1, k2, k3, k4, kcal = st.columns([1.4, 1.4, 1.4, 1.4, 2.2])

    if not attendance_df.empty:
        dates = sorted(attendance_df["Date"].unique(), reverse=True)
        default_dt = dates[0]
        if isinstance(default_dt, pd.Timestamp):
            cal_focus_date = default_dt.date()
        elif isinstance(default_dt, date):
            cal_focus_date = default_dt

    with k1:
        staff_val = 0 if attendance_df.empty else len(attendance_df["Employee"].unique())
        st.markdown(f"""
        <div class="kpi-card kpi-green">
            <div class="kpi-title">Total Active Staff</div>
            <div class="kpi-value">{staff_val}</div>
        </div>""", unsafe_allow_html=True)

    with k2:
        p_val = 0 if attendance_df.empty else int(attendance_df["Status"].isin(["Present", "Reviewed"]).sum())
        st.markdown(f"""
        <div class="kpi-card kpi-green">
            <div class="kpi-title">Present Today</div>
            <div class="kpi-value">{p_val}</div>
        </div>""", unsafe_allow_html=True)

    with k3:
        l_val = 0 if attendance_df.empty else int((attendance_df["Status"] == "Late").sum())
        st.markdown(f"""
        <div class="kpi-card kpi-gold">
            <div class="kpi-title">Late</div>
            <div class="kpi-value">{l_val} <span style="color:#F8B81D;font-size:1.3rem;">⚠</span></div>
        </div>""", unsafe_allow_html=True)

    with k4:
        pend_val = 0 if attendance_df.empty else int((attendance_df["Status"] == "Pending review").sum())
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Pending Review</div>
            <div class="kpi-value">{pend_val} <span style="color:#8CA69F;font-size:1.3rem;">◔</span></div>
        </div>""", unsafe_allow_html=True)

    with kcal:
        render_calendar_widget(cal_focus_date)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- MAIN WORKSPACE GRID ---
    main_left, main_right = st.columns([6.3, 3.7])

    with main_left:
        with st.container(border=True):
            if not attendance_df.empty:
                dates = sorted(attendance_df["Date"].unique(), reverse=True)
                selected_date = st.selectbox("Date-picker", dates, key="selected_date_box")
                st.markdown(f"### Daily Attendance ({selected_date})")

                daily_report = attendance_df[attendance_df["Date"] == selected_date].reset_index(drop=True)
                daily_report.index = daily_report.index + 1

                display_df = daily_report.drop(columns=["Timestamp"], errors="ignore").copy()
                display_df.insert(0, "S.No", display_df.index)
                st.dataframe(display_df, use_container_width=True, hide_index=True)

                # Persistent Reviewed action for Pending review rows
                pending_rows = daily_report[daily_report["Status"] == "Pending review"]
                if not pending_rows.empty:
                    st.markdown("#### Mark Pending as Reviewed")
                    pending_choices = [
                        f"{row['Employee']} ({row['Time']})"
                        for _, row in pending_rows.iterrows()
                    ]
                    selected_pending = st.multiselect(
                        "Select employees to mark as Reviewed (permanently saved in your private workspace)",
                        options=pending_choices,
                        key=f"pending_review_{selected_date}",
                    )
                    b_col1, b_col2 = st.columns([1.2, 1.8])
                    with b_col1:
                        if st.button("✅ Mark Selected as Reviewed", use_container_width=True, disabled=not selected_pending):
                            for item in selected_pending:
                                emp_name = item.rsplit(" (", 1)[0].strip()
                                reviewed_map[f"{selected_date}|{emp_name}"] = True
                            save_reviewed_map(user_workspace, reviewed_map)
                            st.rerun()
                    with b_col2:
                        if st.button("✓ Mark All Pending Today as Reviewed", use_container_width=True):
                            for _, row in pending_rows.iterrows():
                                emp_name = str(row["Employee"]).strip()
                                reviewed_map[f"{selected_date}|{emp_name}"] = True
                            save_reviewed_map(user_workspace, reviewed_map)
                            st.rerun()
            else:
                st.markdown("### Daily Attendance")
                st.info("Upload your WhatsApp Attendance (.zip) file from the sidebar to view daily records.")

    with main_right:
        with st.container(border=True):
            s_col1, s_col2 = st.columns([1.4, 1])
            with s_col1:
                st.markdown("### Daily Shareable Summary")
            with s_col2:
                st.markdown(
                    "<div style='background:#4CAF50;color:#081A16;font-weight:700;"
                    "padding:6px 10px;border-radius:8px;text-align:center;font-size:0.82rem;'>"
                    "Copy to WhatsApp</div>",
                    unsafe_allow_html=True,
                )

            if not daily_report.empty and selected_date is not None:
                report_text = generate_shareable_report(daily_report, selected_date)
                st.text_area("WhatsApp Report", report_text, height=195, label_visibility="collapsed")
            else:
                st.text_area("WhatsApp Report", "No daily report generated yet.", height=195, label_visibility="collapsed")

        with st.container(border=True):
            st.markdown("### Export Actions")

            if not daily_report.empty and selected_date is not None:
                csv_data = daily_report.drop(columns=["Timestamp"], errors="ignore").to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="⬇  Download CSV",
                    data=csv_data,
                    file_name=f"{current_user}_attendance_{selected_date}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            else:
                st.button("⬇  Download CSV", disabled=True, use_container_width=True)

            monthly_summary_df = pd.DataFrame()
            selected_month = None
            if not attendance_df.empty:
                attendance_df["Month"] = pd.to_datetime(attendance_df["Date"]).dt.to_period("M").astype(str)
                months = sorted(attendance_df["Month"].unique(), reverse=True)
                selected_month = months[0]
                monthly_summary_df = rules.calculate_monthly_attendance(attendance_df, selected_month, user_workspace)

            if not monthly_summary_df.empty and selected_month is not None:
                monthly_csv = monthly_summary_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="%  Download Monthly Summary %",
                    data=monthly_csv,
                    file_name=f"{current_user}_monthly_{selected_month}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            else:
                st.button("%  Download Monthly Summary %", disabled=True, use_container_width=True)

    # --- MONTHLY ATTENDANCE SUMMARY SECTION ---
    if not attendance_df.empty:
        with st.container(border=True):
            st.header("📊 Monthly Attendance Summary (%)")
            months = sorted(attendance_df["Month"].unique(), reverse=True)
            chosen_month = st.selectbox("Select Month for Overall Percentage", months, key="monthly_picker")
            m_df = rules.calculate_monthly_attendance(attendance_df, chosen_month, user_workspace)

            if not m_df.empty:
                m_df = m_df.reset_index(drop=True)
                m_df.index = m_df.index + 1
                st.dataframe(
                    m_df,
                    use_container_width=True,
                    column_config={
                        "Attendance %": st.column_config.ProgressColumn(
                            "Attendance %",
                            format="%.2f%%",
                            min_value=0,
                            max_value=100,
                        )
                    },
                )
                st.text_area(
                    "Monthly WhatsApp Summary",
                    generate_monthly_shareable_report(m_df, chosen_month),
                    height=160,
                )
