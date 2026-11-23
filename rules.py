import os
import pandas as pd

def apply_attendance_rules(df, shift_start="09:00", grace_minutes=30):
    if df.empty:
        return df
    
    # Isolate the first check-in per employee per day to prevent duplicates
    daily_first = df.sort_values('Timestamp').groupby(['Date', 'Employee']).first().reset_index()
    
    # Calculate late threshold
    daily_first['Shift_Start'] = pd.to_datetime(daily_first['Date'].astype(str) + ' ' + shift_start)
    daily_first['Late_Threshold'] = daily_first['Shift_Start'] + pd.Timedelta(minutes=grace_minutes)
    
    def determine_status(row):
        if not row['Has_Media']:
            return "Pending review"
        elif row['Timestamp'] <= row['Late_Threshold']:
            return "Present"
        else:
            return "Late"
            
    daily_first['Status'] = daily_first.apply(determine_status, axis=1)
    return daily_first[['Date', 'Employee', 'Time', 'Has_Media', 'Status', 'Timestamp']]


def calculate_monthly_attendance(attendance_df, selected_month, workspace_dir):
    if attendance_df.empty:
        return pd.DataFrame()

    df = attendance_df.copy()
    df['Month'] = pd.to_datetime(df['Date']).dt.to_period('M').astype(str)
    month_df = df[df['Month'] == selected_month]

    if month_df.empty:
        return pd.DataFrame()

    total_working_days = month_df['Date'].nunique()

    # Read employees.csv ONLY from this user's private workspace
    employees_csv = os.path.join(workspace_dir, "employees.csv")
    if os.path.exists(employees_csv):
        emp_df = pd.read_csv(employees_csv)
        name_col = 'Name' if 'Name' in emp_df.columns else emp_df.columns[0]
        all_employees = emp_df[name_col].dropna().unique().tolist()
    else:
        all_employees = month_df['Employee'].unique().tolist()

    summary_rows = []
    for emp in all_employees:
        emp_records = month_df[month_df['Employee'] == emp]
        present_days = (emp_records['Status'] == 'Present').sum()
        late_days = (emp_records['Status'] == 'Late').sum()
        approved_leaves = (emp_records['Status'] == 'Approved leave').sum()
        pending_days = (emp_records['Status'] == 'Pending review').sum()

        attended_days = present_days + late_days + approved_leaves
        absent_days = max(0, total_working_days - (attended_days + pending_days))
        attendance_pct = round((attended_days / total_working_days) * 100, 2) if total_working_days > 0 else 0.0

        summary_rows.append({
            "Employee": emp,
            "Total Working Days": total_working_days,
            "Present": int(present_days),
            "Late": int(late_days),
            "Approved Leave": int(approved_leaves),
            "Pending Review": int(pending_days),
            "Absent": int(absent_days),
            "Attendance %": attendance_pct
        })

    return pd.DataFrame(summary_rows).sort_values(by="Attendance %", ascending=False)