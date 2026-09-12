# Smart Campus Management System — Firebase Edition

A Flask-based Smart Campus Management & Student Assistance System using Firebase Authentication and Cloud Firestore.

## Quick Start (Windows)

### 1. Firebase
Create a Firebase project and enable:
- Authentication → Sign-in method → Email/Password
- Cloud Firestore → Create database

When creating the database, choose the `(default)` database ID. The app reads
`FIRESTORE_DATABASE_ID` from `.env` if you use a named database instead.

Create a **new** Firebase/Google service-account key and save it in this project as:
`serviceAccountKey.json`

> Never commit this file. If an old key was exposed, revoke it and create a new one.

### 2. Firebase Web API key
Firebase Console → Project settings → General → Your apps → Web app → copy the Web API Key.
Do not leave `your_firebase_web_api_key` in `.env`; that placeholder allows registration
through the Admin SDK but cannot authenticate password logins.

Put it in `.env`:

```env
FIREBASE_SERVICE_ACCOUNT=./serviceAccountKey.json
FIREBASE_WEB_API_KEY=YOUR_FIREBASE_WEB_API_KEY
FLASK_SECRET_KEY=replace-with-a-long-random-secret
```

### 3. Install
Double-click `setup.bat`, or run:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 4. Run

```powershell
python app.py
```

Open http://127.0.0.1:5000

## Demo Accounts
- Admin: `admin@campus.local` / `admin123`
- Student: `student@campus.local` / `student123`
- Faculty: `faculty@campus.local` / `faculty123`

The app creates/reuses these Firebase Authentication accounts on first startup.

## Firestore
The server-side Flask app uses the Firebase Admin SDK. The SQL-shaped application layer uses in-memory SQLite for compatibility; persistent data is synchronized to Firestore.

## Existing SQLite migration
If you have the original `smart_campus.db`:

```powershell
$env:FIREBASE_SERVICE_ACCOUNT="./serviceAccountKey.json"
$env:FIREBASE_MIGRATION_PASSWORD="ChangeMe123!"
python migrate_sqlite_to_firebase.py ./smart_campus.db
```

Migrated users receive the temporary migration password and should change it immediately.

## Security
Never commit:
- `.env`
- `serviceAccountKey.json`
- Firebase private keys
- database files

For deployment, use a production WSGI server and HTTPS.
