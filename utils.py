# utils.py

from datetime import datetime
import pytz

def get_current_time_utc():
    """Get current UTC time in YYYY-MM-DD HH:MM:SS format."""
    return datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')

def format_tally_date(date_str):
    """Convert date string to Tally's expected format."""
    try:
        if isinstance(date_str, str):
            if '-' in date_str:
                day, month, year = date_str.split('-')
            else:
                day = date_str[:2]
                month = date_str[2:4]
                year = date_str[4:]
            return f"{year}{month}{day}"
    except Exception as e:
        print(f"Date formatting error: {e}")
    return date_str