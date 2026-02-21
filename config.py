class Config:
    MYSQL_HOST = "localhost"
    MYSQL_USER = "root"
    MYSQL_PASSWORD = ""
    MYSQL_DB = "expenso_db"
    SECRET_KEY = "secret_key_756"

    # Required for sending OTP by email (forgot credentials). Fill these to receive OTP in email.
    # Gmail: use an App Password (not your normal password). Enable 2FA, then create App Password at myaccount.google.com
    MAIL_SERVER = ""   # e.g. "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USERNAME = "" # your email e.g. "you@gmail.com"
    MAIL_PASSWORD = "" # your app password or SMTP password
    MAIL_DEFAULT_SENDER = ""  # optional, defaults to MAIL_USERNAME

    # Optional: For sending OTP by SMS (forgot credentials). Get these from twilio.com/console
    TWILIO_ACCOUNT_SID = ""
    TWILIO_AUTH_TOKEN = ""
    TWILIO_FROM_NUMBER = ""  # e.g. "+1234567890" (your Twilio phone number)

    # Set to True only for local dev to show OTP in API response (no email sent). False = OTP only in email/phone.
    FORGOT_OTP_DEV_SHOW = False