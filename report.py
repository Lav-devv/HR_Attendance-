def generate_shareable_report(daily_df, selected_date):
    report_text = f"*Attendance Report: {selected_date}*\n\n"
    for _, row in daily_df.iterrows():
        media_flag = "📸 Verified" if row['Has_Media'] else "⚠️ Missing Selfie/Geotag"
        report_text += f"- {row['Employee']}: {row['Status']} at {row['Time']} [{media_flag}]\n"
    return report_text


def generate_monthly_shareable_report(monthly_df, selected_month):
    report_text = f"*Monthly Attendance Summary ({selected_month})*\n"
    working_days = monthly_df['Total Working Days'].iloc[0] if not monthly_df.empty else 0
    report_text += f"_Total Working Days: {working_days}_\n\n"
    
    for _, row in monthly_df.iterrows():
        badge = "🟢" if row['Attendance %'] >= 85 else ("🟡" if row['Attendance %'] >= 75 else "🔴")
        report_text += (
            f"{badge} *{row['Employee']}*: *{row['Attendance %']}%* "
            f"(Present: {row['Present']}, Late: {row['Late']}, Absent: {row['Absent']})\n"
        )
    return report_text