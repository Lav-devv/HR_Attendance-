import re
from datetime import datetime
import pandas as pd

def parse_chat(raw_bytes):
    # Decode raw bytes safely (handles UTF-8, UTF-8-SIG, and UTF-16)
    if isinstance(raw_bytes, bytes):
        if raw_bytes.startswith((b'\xff\xfe', b'\xfe\xff')) or b'\x00' in raw_bytes[:50]:
            text = raw_bytes.decode("utf-16", errors="ignore")
        else:
            text = raw_bytes.decode("utf-8-sig", errors="ignore")
    else:
        text = str(raw_bytes)

    # Remove null bytes and invisible directional marks
    text = text.replace('\x00', '')
    text = re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]', '', text)
    # Normalize special spaces (like \u202f before AM/PM) into normal space
    text = re.sub(r'[\u00a0\u202f\u2000-\u200a]', ' ', text)

    # Match WhatsApp timestamps: [11/11/26, 9:26:45 AM] or 11/11/26, 9:26 AM -
    pattern = re.compile(
        r'(?:\[)?(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)(?:\]|\s*-)\s*([^:\[\]\r\n]+?):\s*(.*?)(?=(?:\s*(?:\[)?\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2})|$)',
        re.DOTALL
    )

    formats = [
        "%m/%d/%y %I:%M:%S %p",
        "%d/%m/%y %I:%M:%S %p",
        "%m/%d/%Y %I:%M:%S %p",
        "%d/%m/%Y %I:%M:%S %p",
        "%m/%d/%y %I:%M %p",
        "%d/%m/%y %I:%M %p",
        "%m/%d/%Y %I:%M %p",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%y %H:%M",
        "%d/%m/%Y %H:%M",
    ]

    data = []
    for match in pattern.finditer(text):
        date_str, time_str, sender, message = match.groups()
        sender = sender.strip()
        message = message.strip()

        # Skip WhatsApp system notifications
        if (
            sender.startswith("-")
            or "created the group" in message
            or "added You" in message
            or "end-to-end encrypted" in message
        ):
            continue

        # Check media attachments or WhatsApp placeholders
        has_file = bool(re.search(r'\.(jpg|jpeg|png|webp|mp4|opus)', message, re.IGNORECASE))
        has_placeholder = any(
            tag in message.lower()
            for tag in ["<image omitted>", "<media omitted>", "image omitted", "[image]", "(file attached)"]
        )
        has_media = has_file or has_placeholder

        dt_str = f"{date_str.strip()} {time_str.strip().upper()}"
        ts = None
        for fmt in formats:
            try:
                ts = datetime.strptime(dt_str, fmt)
                break
            except ValueError:
                continue

        if ts is not None:
            data.append({
                "Date": ts.date(),
                "Time": time_str.strip(),
                "Employee": sender,
                "Message": message,
                "Has_Media": has_media,
                "Timestamp": pd.Timestamp(ts)
            })

    df = pd.DataFrame(data)
    if not df.empty:
        # Mark entire day Has_Media=True if employee sent image in a separate message
        df['Has_Media'] = df.groupby(['Date', 'Employee'])['Has_Media'].transform('any')

    return df