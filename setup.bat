@echo off
setlocal
cd /d %~dp0
if not exist venv python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env >nul
echo.
echo Setup complete.
echo 1. Put your NEW Firebase service account key here as serviceAccountKey.json
 echo 2. Edit .env and set FIREBASE_WEB_API_KEY and FLASK_SECRET_KEY
 echo 3. Run run.bat
pause
