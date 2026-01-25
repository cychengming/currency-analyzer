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

def send_email_alert(pair, alert_info, alert_type='percentage_change'):
    """Send email alert"""
    from modules.database import get_setting
    
    try:
        alert_email = get_setting('alert_email', '')
        if not alert_email:
            return False
        
        subject = '[ALERT] Currency Alert: ' + pair + ' (' + alert_type + ')'
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        period = str(get_setting('detection_period', 30))
        
        percent_change = alert_info.get('percent_change') if isinstance(alert_info, dict) else None
        old_rate = alert_info.get('old_rate') if isinstance(alert_info, dict) else None
        new_rate = alert_info.get('new_rate') if isinstance(alert_info, dict) else None
        current_rate = alert_info.get('current_rate') if isinstance(alert_info, dict) else None
        start_date = alert_info.get('start_date') if isinstance(alert_info, dict) else None
        end_date = alert_info.get('end_date') if isinstance(alert_info, dict) else None

        body_parts = [
            '<html><body style="font-family: Arial, sans-serif; padding: 20px;">',
            '<h1 style="color: #2563eb;">Currency Alert</h1>',
            '<div style="background-color: #f0fdf4; padding: 15px; border-left: 4px solid #10b981;">',
            '<h2 style="color: #10b981;">' + pair + '</h2>',
            '<p><strong>Alert Type:</strong> ' + alert_type + '</p>'
        ]

        if percent_change is not None:
            body_parts.append('<p style="font-size: 20px;"><strong>Change:</strong> <span style="color: #10b981;">' + str(percent_change) + '%</span></p>')
        if current_rate is not None:
            body_parts.append('<p><strong>Current Rate:</strong> ' + str(current_rate) + '</p>')
        if old_rate is not None and new_rate is not None:
            body_parts.append('<p><strong>Rate:</strong> ' + str(old_rate) + ' → ' + str(new_rate) + '</p>')
        if start_date and end_date:
            body_parts.append('<p><strong>Period:</strong> ' + start_date + ' → ' + end_date + '</p>')
        else:
            body_parts.append('<p><strong>Period:</strong> ' + period + ' days</p>')

        body_parts.extend([
            '</div>',
            '<p style="color: #6b7280; margin-top: 20px; font-size: 12px;">Alert sent at: ' + timestamp + '</p>',
            '</body></html>'
        ])

        body = ''.join(body_parts)
        
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
