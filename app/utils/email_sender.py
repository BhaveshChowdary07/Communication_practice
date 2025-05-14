import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import url_for

# --- TEMPORARY GMAIL SMTP CONFIG ---
GMAIL_USER = 'sreebhavesh7@gmail.com'
GMAIL_PASS = 'dwab bxay jojt naho'

def send_credentials(email, password, test_id):
    subject = "Your Communication Test Login"
    body = f"""
Hello,

You have been assigned a communication test.

Login Email: {email}
Password: {password}
Test ID: {test_id}

You can log in to take the test at: http://127.0.0.1:5000/student/login

Thanks,
Test Platform Team
"""

    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        raise Exception(f"Failed to send email to {email}: {str(e)}")