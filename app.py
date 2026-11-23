import os
import zipfile
import importlib
import inspect
import pandas as pd
import streamlit as st
import rules

# Force reload rules.py so Streamlit never uses stale cached functions
importlib.reload(rules)

from parser import parse_chat
from report import generate_shareable_report, generate_monthly_shareable_report
from auth import register_user, authenticate_user, get_user_workspace, delete_user_data

st.set_page_config(page_title="TechNaka Private Attendance Analyzer", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None

# --- LOGIN / REGISTER GATE ---
if not st.session_state.authenticated or not st.session_state.username:
    st.title("🔒 WhatsApp Attendance Analyzer")
    st.caption("Private Workspace: Your uploads and employee records are isolated to your account.")

    tab_login, tab_register = st.tabs(["Login", "Create Account"])

    with tab_login:
        with st.form("login_form"):
            login_user = st.text_input("Username")
            login_pass = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
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
            reg_submitted = st.form_submit_button("Register")
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

    with st.sidebar:
        st.markdown(f"### 👤 Logged in as: `{current_user}`")
        st.info("Your data is stored in an isolated workspace and is invisible to other users.")

        st.subheader("Private Employee Roster")
        emp_upload = st.file_uploader("Upload your employees.csv", type=["csv"], key="emp_csv")
        if emp_upload is not None:
            with open(private_emp_path, "wb") as f:
                f.write(emp_upload.getbuffer())
            st.success("Saved to your private workspace!")

        if os.path.exists(private_emp_path):
            st.caption("✅ Custom `employees.csv` active")
        else:
            st.caption("ℹ️ Using names detected from chat")

        st.divider()
        if st.button("🗑️ Wipe My Private Data"):
            delete_user_data(current_user)
            st.success("All your workspace files have been deleted.")
            st.rerun()

        if st.button("🚪 Logout"):
            st.session_state.clear()
            st.rerun()

    st.title("WhatsApp Attendance Analyzer (Private Workspace)")
    st.markdown("Upload your WhatsApp exported **ZIP file** (containing `_chat.txt` and media attachments).")

    uploaded_zip = st.file_uploader("Upload WhatsApp Chat ZIP Export", type=["zip"])

    if uploaded_zip is not None:
        try:
            with zipfile.ZipFile(uploaded_zip, "r") as z:
                all_files = [
                    name for name in z.namelist()
                    if not name.startswith("__MACOSX/") and not name.endswith("/")
                ]
                txt_filenames = [name for name in all_files if name.lower().endswith(".txt")]

                if not txt_filenames:
                    st.error(f"No .txt chat file found inside ZIP. Files detected inside ZIP: {all_files}")
                else:
                    target_txt = next((n for n in txt_filenames if "_chat.txt" in n.lower()), txt_filenames[0])
                    with z.open(target_txt) as f:
                        raw_bytes = f.read()

                    chat_df = parse_chat(raw_bytes)

                    if not chat_df.empty:
                        # Safely check if rules.py accepts workspace_dir
                        sig = inspect.signature(rules.apply_attendance_rules)
                        if "workspace_dir" in sig.parameters:
                            attendance_df = rules.apply_attendance_rules(chat_df, workspace_dir=user_workspace)
                        else:
                            attendance_df = rules.apply_attendance_rules(chat_df)

                        dates = sorted(attendance_df['Date'].unique(), reverse=True)
                        selected_date = st.selectbox("Select Date to Review", dates)
                        
                        # Reset serial index to start from 1, 2, 3...
                        daily_report = attendance_df[attendance_df['Date'] == selected_date].reset_index(drop=True)
                        daily_report.index = daily_report.index + 1

                        st.subheader(f"Daily Attendance: {selected_date}")
                        st.dataframe(daily_report.drop(columns=['Timestamp']), use_container_width=True)

                        col1, col2 = st.columns(2)
                        with col1:
                            st.subheader("Daily Shareable Summary")
                            report_text = generate_shareable_report(daily_report, selected_date)
                            st.text_area("Copy daily report to WhatsApp:", report_text, height=220)

                        with col2:
                            st.subheader("Daily Data Export")
                            csv = daily_report.drop(columns=['Timestamp']).to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="Download Daily CSV",
                                data=csv,
                                file_name=f"{current_user}_attendance_{selected_date}.csv",
                                mime="text/csv"
                            )

                        st.divider()

                        st.header("📊 Monthly Attendance Summary (%)")
                        attendance_df['Month'] = pd.to_datetime(attendance_df['Date']).dt.to_period('M').astype(str)
                        months = sorted(attendance_df['Month'].unique(), reverse=True)
                        selected_month = st.selectbox("Select Month for Overall Percentage", months)

                        monthly_summary_df = rules.calculate_monthly_attendance(attendance_df, selected_month, user_workspace)

                        if not monthly_summary_df.empty:
                            st.dataframe(
                                monthly_summary_df,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Attendance %": st.column_config.ProgressColumn(
                                        "Attendance %",
                                        format="%.2f%%",
                                        min_value=0,
                                        max_value=100,
                                    )
                                }
                            )

                            m_col1, m_col2 = st.columns(2)
                            with m_col1:
                                st.subheader("Monthly Shareable Summary")
                                monthly_report_text = generate_monthly_shareable_report(monthly_summary_df, selected_month)
                                st.text_area("Copy monthly report to WhatsApp:", monthly_report_text, height=220)

                            with m_col2:
                                st.subheader("Monthly Data Export")
                                monthly_csv = monthly_summary_df.to_csv(index=False).encode('utf-8')
                                st.download_button(
                                    label="Download Monthly Percentage CSV",
                                    data=monthly_csv,
                                    file_name=f"{current_user}_monthly_{selected_month}.csv",
                                    mime="text/csv"
                                )
                    else:
                        st.warning("Chat file opened, but no valid messages matched the date/time format.")
                        st.code(raw_bytes[:400].decode("utf-8", errors="replace"))
        except Exception as e:
            st.error(f"Error reading ZIP file: {e}")