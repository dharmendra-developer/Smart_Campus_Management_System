# Smart Campus Deployment Guide

This project is ready for GitHub and deployment-friendly hosting.

## 1) GitHub setup

```bash
git init
git add .
git commit -m "Initial project setup"
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO>.git
git push -u origin main
```

## 2) Important files not to commit

Do not commit these secrets or local artifacts:
- .env
- serviceAccountKey.json
- .venv/
- venv/
- *.db

They are already ignored in `.gitignore`.

## 3) Deployment target

This is a Flask app, so it should be deployed on a Python host such as:
- Render
- Railway
- Fly.io
- PythonAnywhere
- Azure App Service

GitHub Pages is not suitable for a Flask app.

## 4) Render deployment

Use these settings:
- Build command:
  ```bash
  pip install -r requirements.txt
  ```
- Start command:
  ```bash
  gunicorn app:app
  ```

Set environment variables in the hosting dashboard:
- FLASK_SECRET_KEY=your-long-random-secret
- USE_FIRESTORE=false
- FIREBASE_WEB_API_KEY=your_web_api_key_if_using_firebase_auth
- FIREBASE_SERVICE_ACCOUNT=./serviceAccountKey.json
- FIRESTORE_DATABASE_ID=(default)

## 5) Local run

```bash
python app.py
```

Open:
```text
http://127.0.0.1:5000
```
