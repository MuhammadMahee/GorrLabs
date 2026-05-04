from flask import Flask, render_template, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
            template_folder=BASE_DIR,
            static_folder=BASE_DIR,
            static_url_path="/static")

SMTP_SERVER   = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = "gorrlabs@gmail.com"
SMTP_PASSWORD = "oyxt vvxv rmvw hsvg"  # ⚠️ replace this
RECIPIENT     = "gorrlabs@gmail.com"


def send_email(name, email, message):
    msg = MIMEMultipart("alternative")
    
    msg["Subject"] = "Gorr Labs — We received your message"
    msg["From"] = SMTP_USER
    msg["To"] = email                  # ✅ user gets email
    msg["Cc"] = RECIPIENT              # ✅ you get CC

    recipients = [email, RECIPIENT]    # ✅ must include both

    html = f"""
    <html>
    <body style="font-family:Arial,sans-serif;background:#0A0A0A;color:#fff;padding:30px;">
      <div style="max-width:600px;margin:auto;background:#111;border:1px solid #FF7A00;
                  border-radius:12px;padding:30px;text-align:center;">

        <!-- LOGO -->
        <img src="https://gorrlabs.vercel.app/static/logo.png"
             alt="Gorr Labs"
             style="width:120px;margin-bottom:20px;">

        <h2 style="color:#FF7A00;">Gorr Labs</h2>

        <p style="text-align:left;">Hi {name},</p>

        <p style="text-align:left;">
          We’ve received your message and will get back to you within 24 hours.
        </p>

        <hr style="border-color:#333;margin:20px 0;">

        <p style="text-align:left;"><strong>Your Message:</strong></p>

        <p style="background:#1a1a1a;padding:16px;border-left:3px solid #FF2D2D;
                  border-radius:6px;line-height:1.7;text-align:left;">
          {message}
        </p>

        <hr style="border-color:#333;margin:20px 0;">

        <p style="font-size:12px;color:#777;text-align:left;">
          Submitted Email: {email}<br>
          This is an automated confirmation from Gorr Labs.
        </p>

      </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.sendmail(SMTP_USER, recipients, msg.as_string())


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/send-message", methods=["POST"])
def send_message():
    data = request.get_json() or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    message = data.get("message", "").strip()

    if not name or not email or not message:
        return jsonify({"success": False, "error": "All fields are required."}), 400

    try:
        send_email(name, email, message)
        return jsonify({
            "success": True,
            "message": "Message sent! We'll get back to you within 24 hours."
        })
    except Exception as e:
        print("Email error:", e)
        return jsonify({
            "success": True,
            "message": "Message received! We'll be in touch soon."
        })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
