# Gorr Labs — Vercel Deployment Guide

## Project Structure

```
GorrLabs-main/
├── api/
│   └── index.py              # Flask app (Vercel entry point)
├── public/
│   ├── index.html            # Home page
│   ├── contact.html          # Contact page
│   └── static/
│       └── assets/
│           ├── logo.png
│           └── logo_orange.png
├── vercel.json               # Vercel configuration
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
└── VERCEL_DEPLOYMENT.md      # This file
```

## Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub Account**: Your repository should be on GitHub
3. **Gmail App Password**: For email functionality

## Step 1: Set Up Gmail App Password

The Flask app sends emails using Gmail SMTP. You need a secure app password:

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Factor Authentication** (if not already enabled)
3. Scroll down to **App Passwords** (only appears if 2FA is enabled)
4. Select **Mail** and **Windows Computer** (or your device type)
5. Google will generate a **16-character password**
6. **Copy this password** — you'll use it in Vercel environment variables

## Step 2: Push Code to GitHub

Make sure your code is pushed to GitHub:

```bash
git add .
git commit -m "Set up Vercel deployment configuration"
git push origin master
```

## Step 3: Deploy to Vercel

### Option A: Using Vercel CLI (Recommended)

1. **Install Vercel CLI**:
   ```bash
   npm install -g vercel
   ```

2. **Deploy**:
   ```bash
   vercel
   ```
   Follow the prompts to:
   - Link to your GitHub account
   - Select the project
   - Confirm deployment settings

3. **Add Environment Variables**:
   When prompted or via Vercel Dashboard:
   ```
   SMTP_USER=your_gmail@gmail.com
   SMTP_PASSWORD=your_16char_app_password
   RECIPIENT_EMAIL=gorrlabs@gmail.com
   ```

### Option B: Using Vercel Dashboard

1. Go to [vercel.com/dashboard](https://vercel.com/dashboard)
2. Click **"Add New Project"**
3. Select your GitHub repository
4. Click **"Import"**
5. Under **Environment Variables**, add:
   - `SMTP_USER`: your Gmail address
   - `SMTP_PASSWORD`: your Gmail app password (16 chars)
   - `RECIPIENT_EMAIL`: email to receive submissions
6. Click **"Deploy"**

## Step 4: Test Your Deployment

After deployment completes:

1. Visit your Vercel URL (e.g., `https://gorrlabs-12345.vercel.app`)
2. Check the home page loads correctly
3. Go to `/contact` and test the contact form
4. Submit a test message and verify:
   - ✅ Success message appears
   - ✅ Email received in `RECIPIENT_EMAIL` inbox
   - ✅ Confirmation email sent to submitted email address

## API Endpoints

- `GET /` — Home page (index.html)
- `GET /contact` — Contact page (contact.html)
- `POST /api/send-message` — Submit contact form

**Request Body** (JSON):
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "message": "Your message here"
}
```

## Troubleshooting

### Email Not Sending

1. **Check environment variables** in Vercel Dashboard:
   - Settings → Environment Variables
   - Verify `SMTP_USER`, `SMTP_PASSWORD`, `RECIPIENT_EMAIL`

2. **Verify Gmail app password**:
   - Is it exactly 16 characters?
   - Did you copy it correctly (no spaces)?
   - Is 2FA enabled on your Google account?

3. **Check deployment logs**:
   - Vercel Dashboard → Deployments → Click latest deployment
   - Scroll to "Runtime logs" and check for errors

### Pages Not Loading

1. Check `public/` folder has `index.html` and `contact.html`
2. Verify template paths in `api/index.py` are correct
3. Check Vercel logs for Flask errors

### 404 Errors

Make sure the `vercel.json` configuration is correct and includes Python 3.11 runtime.

## Custom Domain

To add your own domain:

1. Vercel Dashboard → Project Settings → Domains
2. Add your domain (e.g., `gorrlabs.com`)
3. Follow DNS configuration instructions for your domain provider
4. Update the logo URL in email template if needed:
   ```python
   # In api/index.py, update:
   <img src="https://your-domain.com/static/assets/logo.png"
   ```

## Local Development

To test locally before deploying:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SMTP_USER="your_gmail@gmail.com"
export SMTP_PASSWORD="your_16char_app_password"
export RECIPIENT_EMAIL="gorrlabs@gmail.com"

# Run Flask
python api/index.py
```

Visit `http://localhost:5000`

## Important Security Notes

⚠️ **Never commit your actual credentials to GitHub!**

- Use Vercel's Environment Variables for sensitive data
- The `.env.example` file shows the format, but don't put real values there
- If you accidentally committed credentials:
  1. Regenerate your Gmail app password immediately
  2. Update environment variables in Vercel

## Next Steps

- [ ] Generate Gmail app password
- [ ] Push code to GitHub
- [ ] Deploy via Vercel CLI or Dashboard
- [ ] Add environment variables in Vercel
- [ ] Test the contact form
- [ ] (Optional) Configure custom domain

Questions? Check [Vercel Docs](https://vercel.com/docs) or email support.
