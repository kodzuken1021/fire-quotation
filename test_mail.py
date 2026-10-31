import os, smtplib
from dotenv import load_dotenv
load_dotenv()
user, pw = os.environ["MAIL_USERNAME"], os.environ["MAIL_PASSWORD"].replace(" ", "")
for port in (587, 465):
    try:
        if port == 465:
            s = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15)
        else:
            s = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
            s.starttls()
        s.login(user, pw)
        print(port, "LOGIN OK")
        s.quit()
    except Exception as e:
        print(port, "FAILED:", type(e).__name__, e)