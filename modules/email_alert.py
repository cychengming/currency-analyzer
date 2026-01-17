"""
Email alert module - Send email notifications
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

SMTP_HOST = os.environ.get('SMTP_HOST', 'mail.smtp2go.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
SMTP_FROM = os.environ.get('SMTP_FROM', '')
SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true'
SMTP_USE_SSL = os.environ.get('SMTP_USE_SSL', 'false').lower() == 'true'

# Backward-compatible Gmail fallback
GMAIL_USER = os.environ.get('GMAIL_USER', '')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_PASSWORD', '')

def send_email_alert(pair, trend_info):
    """Send email alert"""
    from modules.database import get_setting
    
    try:
        alert_email = get_setting('alert_email', '')
        if not alert_email:
            return False
        
        subject = '[ALERT] Currency Alert: ' + pair + ' Uptrend Detected!'
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        period = str(get_setting('detection_period', 30))
        
        body = """<html><body style="font-family: Arial, sans-serif; padding: 20px;"><h1 style="color: #2563eb;">Currency Uptrend Alert</h1><div style="background-color: #f0fdf4; padding: 15px; border-left: 4px solid #10b981;"><h2 style="color: #10b981;">""" + pair + """</h2><p style="font-size: 24px;"><strong>Change:</strong> <span style="color: #10b981;">+""" + str(trend_info['percent_change']) + """%</span></p></div><div style="margin-top: 20px;"><p><strong>Start Rate (""" + trend_info['start_date'] + """):</strong> """ + str(trend_info['old_rate']) + """</p><p><strong>Current Rate (""" + trend_info['end_date'] + """):</strong> """ + str(trend_info['new_rate']) + """</p><p><strong>Period:</strong> """ + period + """ days</p></div><p style="color: #6b7280; margin-top: 20px; font-size: 12px;">Alert sent at: """ + timestamp + """</p></body></html>"""
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        from_address = SMTP_FROM or SMTP_USER or GMAIL_USER
        msg['From'] = from_address
        msg['To'] = alert_email
        msg.attach(MIMEText(body, 'html'))

        # Prefer SMTP provider credentials when set
        if SMTP_USER and SMTP_PASS:
            if SMTP_USE_SSL:
                with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                    server.login(SMTP_USER, SMTP_PASS)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                    if SMTP_USE_TLS:
                        server.starttls()
                    server.login(SMTP_USER, SMTP_PASS)
                    server.send_message(msg)
        elif GMAIL_USER and GMAIL_APP_PASSWORD:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                server.send_message(msg)
        else:
            raise Exception('No SMTP credentials configured')
        
        print('[OK] Email sent for ' + pair)
        return True
    except Exception as e:
        print('[ERROR] Error sending email: ' + str(e))
        return False
