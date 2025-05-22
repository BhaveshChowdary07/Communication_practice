import requests

EMAIL_API_URL = "https://submissions.azurewebsites.net/api/sendEmail"

def send_credentials(email, password, test_id):
    subject = "Your Communication Test Login"
    render_base_url = "https://communication-practice.onrender.com/"
    body = f"""
Hello,<br><br>
You have been assigned a communication test.<br><br>
<b>Login Email:</b> {email}<br>
<b>Password:</b> {password}<br>
<b>Test ID:</b> {test_id}<br><br>
You can log in to take the test at: <a href="https://www.practicetests.in/student/login">
Click here to login</a><br><br>
Thanks,<br>
<b>Test Platform Team</b>
"""

    payload = {
        "to": email,
        "subject": subject,
        "body": body
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(EMAIL_API_URL, json=payload, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Failed to send email to {email}. Status: {response.status_code}, Response: {response.text}")
