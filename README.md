# Gorr Labs Website — Flask

## Setup

```bash
pip install -r requirements.txt
```

## Email Configuration

Set these environment variables (or edit app.py for development):

```bash
export SMTP_USER="your_gmail@gmail.com"          # Your Gmail
export SMTP_PASSWORD="your_16char_app_password"  # Gmail App Password
```

### How to get a Gmail App Password:
1. Go to Google Account → Security
2. Enable 2-Factor Authentication
3. Go to App Passwords → create one for "Mail"
4. Use that 16-character password as SMTP_PASSWORD

## Logo

Place your logo file at:
```
static/assets/logo.png
```

## Run

```bash
python app.py
```

Visit: http://localhost:5000

## Routes

- `/`        — Full landing page
- `/contact` — Dedicated contact page
- `/send-message` — POST endpoint for form submissions (sends email to Gorrlabs@gmail.com)

## Folder Structure

```
gorrlabs/
├── app.py
├── requirements.txt
├── templates/
│   ├── index.html     (home page — all CSS+JS inline)
│   └── contact.html   (contact page — all CSS+JS inline)
└── static/
    └── assets/
        └── logo.png   ← put your logo here
```
