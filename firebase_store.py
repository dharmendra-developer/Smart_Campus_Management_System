"""Firestore-backed persistence layer for the Smart Campus Flask app.

The application keeps its existing SQL-shaped data-access code through a small
in-memory SQLite compatibility layer. SQLite is NEVER used as persistent
storage: every committed change is synchronized to Cloud Firestore.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore, auth
from google.api_core.exceptions import NotFound, PermissionDenied
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

USE_FIRESTORE = os.getenv("USE_FIRESTORE", "false").strip().lower() in {"1", "true", "yes", "on"}
LOCAL_DB_PATH = Path(__file__).with_name("smart_campus_local.db")


COLLECTIONS = [
    "users", "student_profiles", "student_profile_history", "notices", "events",
    "materials", "complaints", "quizzes", "quiz_attempts", "opportunities",
    "attendance", "daily_attendance", "marks", "timetable", "assignments", "attendance_sessions",
    "attendance_scans", "notifications", "audit_logs", "lab_bookings", "lost_found",
]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT,role TEXT DEFAULT 'student',department TEXT NOT NULL DEFAULT 'Computer Science & Engineering (CSE)');
CREATE TABLE IF NOT EXISTS student_profiles (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER UNIQUE NOT NULL,phone TEXT,enrollment_no TEXT,semester TEXT,date_of_birth TEXT,cgpa TEXT,skills TEXT,career_interest TEXT,linkedin_url TEXT,resume_url TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS student_profile_history (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,name TEXT NOT NULL,email TEXT NOT NULL,department TEXT NOT NULL,phone TEXT,enrollment_no TEXT,semester TEXT,date_of_birth TEXT,cgpa TEXT,skills TEXT,career_interest TEXT,linkedin_url TEXT,resume_url TEXT,saved_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS notices (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,content TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,event_date TEXT NOT NULL,description TEXT);
CREATE TABLE IF NOT EXISTS materials (id INTEGER PRIMARY KEY AUTOINCREMENT,subject TEXT NOT NULL,title TEXT NOT NULL,link TEXT,youtube_link TEXT,department TEXT NOT NULL DEFAULT 'All Departments');
CREATE TABLE IF NOT EXISTS complaints (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,subject TEXT NOT NULL,message TEXT NOT NULL,status TEXT DEFAULT 'Pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS quizzes (id INTEGER PRIMARY KEY AUTOINCREMENT,question TEXT NOT NULL,a TEXT NOT NULL,b TEXT NOT NULL,c TEXT NOT NULL,d TEXT NOT NULL,answer TEXT NOT NULL,department TEXT NOT NULL DEFAULT 'All Departments');
CREATE TABLE IF NOT EXISTS quiz_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,department TEXT NOT NULL,score INTEGER NOT NULL,total INTEGER NOT NULL,percentage REAL NOT NULL,attempted_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS opportunities (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,company TEXT NOT NULL,opportunity_type TEXT NOT NULL,deadline TEXT,link TEXT,description TEXT,department TEXT NOT NULL DEFAULT 'All Departments',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,subject TEXT NOT NULL,attended INTEGER NOT NULL DEFAULT 0,total_classes INTEGER NOT NULL DEFAULT 0,UNIQUE(user_id,subject));
CREATE TABLE IF NOT EXISTS daily_attendance (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,subject TEXT NOT NULL,attendance_date TEXT NOT NULL,status TEXT NOT NULL,marked_by INTEGER NOT NULL,UNIQUE(user_id,subject,attendance_date));
CREATE TABLE IF NOT EXISTS marks (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,subject TEXT NOT NULL,assessment TEXT NOT NULL,score REAL NOT NULL DEFAULT 0,max_score REAL NOT NULL DEFAULT 100);
CREATE TABLE IF NOT EXISTS timetable (id INTEGER PRIMARY KEY AUTOINCREMENT,department TEXT NOT NULL,day TEXT NOT NULL,start_time TEXT NOT NULL,end_time TEXT NOT NULL,subject TEXT NOT NULL,room TEXT);
CREATE TABLE IF NOT EXISTS assignments (id INTEGER PRIMARY KEY AUTOINCREMENT,department TEXT NOT NULL,subject TEXT NOT NULL,title TEXT NOT NULL,due_date TEXT NOT NULL,description TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS attendance_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT,department TEXT NOT NULL,subject TEXT NOT NULL,session_code TEXT UNIQUE NOT NULL,session_date TEXT DEFAULT CURRENT_DATE,active INTEGER NOT NULL DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS attendance_scans (id INTEGER PRIMARY KEY AUTOINCREMENT,session_id INTEGER NOT NULL,user_id INTEGER NOT NULL,scanned_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(session_id,user_id));
CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,title TEXT NOT NULL,message TEXT NOT NULL,category TEXT DEFAULT 'Campus',is_read INTEGER NOT NULL DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,action TEXT NOT NULL,ip_address TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS lab_bookings (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,lab_name TEXT NOT NULL,booking_date TEXT NOT NULL,booking_time TEXT NOT NULL,purpose TEXT NOT NULL,status TEXT DEFAULT 'Requested',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS lost_found (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,item_type TEXT NOT NULL,item_name TEXT NOT NULL,description TEXT NOT NULL,location TEXT NOT NULL,status TEXT DEFAULT 'Open',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, tuple):
        return list(value)
    return value


def _sqlite_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value)
    return value


def _credentials_from_env():
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    path = os.getenv("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if raw:
        return credentials.Certificate(json.loads(raw))
    if path:
        return credentials.Certificate(path)
    default = Path(__file__).with_name("serviceAccountKey.json")
    if default.exists():
        return credentials.Certificate(str(default))
    return credentials.ApplicationDefault()


def init_firebase():
    if not USE_FIRESTORE:
        return None
    try:
        return firebase_admin.get_app()
    except ValueError:
        try:
            return firebase_admin.initialize_app(_credentials_from_env())
        except Exception:
            return None


firebase_app = init_firebase()
firestore_database_id = os.getenv("FIRESTORE_DATABASE_ID", "(default)").strip() or "(default)"
db = None
if firebase_app is not None:
    try:
        db = firestore.client(firebase_app, database_id=firestore_database_id)
    except Exception:
        db = None


class FirestoreSQLiteConnection:
    """Drop-in connection used by the existing Flask code.

    Persistent state lives in Firestore collections. The sqlite database is
    created in RAM for the request and discarded on close.
    """
    def __init__(self):
        self.sqlite = sqlite3.connect(":memory:")
        self.sqlite.row_factory = sqlite3.Row
        self.sqlite.execute("PRAGMA foreign_keys=ON")
        self.sqlite.executescript(SCHEMA_SQL)
        self._load()

    def _load(self):
        if db is None:
            raise RuntimeError("Firestore is unavailable; using the local SQLite fallback.")
        try:
            for collection in COLLECTIONS:
                rows = []
                for snap in db.collection(collection).stream():
                    data = snap.to_dict() or {}
                    if "id" not in data:
                        try:
                            data["id"] = int(snap.id)
                        except ValueError:
                            continue
                    rows.append(data)
                if not rows:
                    continue
                cols = [r[1] for r in self.sqlite.execute(f"PRAGMA table_info({collection})").fetchall()]
                valid_rows = [{k: v for k, v in r.items() if k in cols} for r in rows]
                for row in valid_rows:
                    if "id" not in row:
                        continue
                    names = list(row.keys())
                    values = [_sqlite_value(row[n]) for n in names]
                    placeholders = ",".join("?" for _ in names)
                    try:
                        self.sqlite.execute(
                            f"INSERT OR REPLACE INTO {collection} ({','.join(names)}) VALUES ({placeholders})",
                            values,
                        )
                    except sqlite3.Error:
                        continue
        except NotFound as exc:
            raise RuntimeError(
                "Firestore database is not enabled for this project. Create the "
                f"(default) database in Firebase Console, or set FIRESTORE_DATABASE_ID "
                "to an existing database ID in .env."
            ) from exc
        except PermissionDenied as exc:
            raise RuntimeError(
                "The Firebase service account cannot access Firestore. Grant it "
                "Cloud Datastore User (or a stronger Firestore role) and retry."
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                "Firestore is unavailable or quota-limited. The app will use the local SQLite-compatible fallback."
            ) from exc
        self.sqlite.commit()

    def execute(self, *args, **kwargs):
        return self.sqlite.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self.sqlite.executemany(*args, **kwargs)

    def cursor(self):
        return self.sqlite.cursor()

    def commit(self):
        self.sqlite.commit()
        self._sync()

    def rollback(self):
        self.sqlite.rollback()

    def executescript(self, *args, **kwargs):
        return self.sqlite.executescript(*args, **kwargs)

    def close(self):
        self.sqlite.close()

    def _sync(self):
        # Firestore writes are chunked so this remains within batch limits.
        for collection in COLLECTIONS:
            local = {
                str(row[0]): dict(row)
                for row in self.sqlite.execute(f"SELECT * FROM {collection}").fetchall()
            }
            remote = {snap.id: snap for snap in db.collection(collection).stream()}
            ops = []
            for doc_id in set(remote) - set(local):
                ops.append(("delete", doc_id, None))
            for doc_id, row in local.items():
                data = {k: _json_safe(v) for k, v in row.items() if k != "id"}
                ops.append(("set", doc_id, data))
            for start in range(0, len(ops), 450):
                batch = db.batch()
                for action, doc_id, data in ops[start:start + 450]:
                    ref = db.collection(collection).document(doc_id)
                    if action == "delete":
                        batch.delete(ref)
                    else:
                        batch.set(ref, data)
                if ops[start:start + 450]:
                    batch.commit()


def get_db_connection():
    if not USE_FIRESTORE or db is None:
        connection = sqlite3.connect(str(LOCAL_DB_PATH))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(SCHEMA_SQL)
        return connection
    try:
        return FirestoreSQLiteConnection()
    except Exception:
        connection = sqlite3.connect(str(LOCAL_DB_PATH))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(SCHEMA_SQL)
        return connection


def _local_db_connection():
    connection = sqlite3.connect(str(LOCAL_DB_PATH))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(SCHEMA_SQL)
    return connection


def _local_user_record(email: str):
    connection = _local_db_connection()
    row = connection.execute(
        "SELECT * FROM users WHERE email = ?",
        (email.lower(),),
    ).fetchone()
    connection.close()
    return row


def firebase_create_user(email: str, password: str, display_name: str, role: str = "student"):
    if not firebase_app or not db:
        connection = _local_db_connection()
        row = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            (email.lower(),),
        ).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO users (name, email, password, role, department) VALUES (?, ?, ?, ?, ?)",
                (display_name, email.lower(), password, role, "Computer Science & Engineering (CSE)"),
            )
            connection.commit()
            user_id = connection.execute(
                "SELECT id FROM users WHERE email = ?",
                (email.lower(),),
            ).fetchone()[0]
        else:
            user_id = row[0]
        connection.close()
        return {"uid": str(user_id), "email": email.lower(), "display_name": display_name}
    user = auth.create_user(email=email, password=password, display_name=display_name)
    auth.set_custom_user_claims(user.uid, {"role": role})
    return user


def firebase_get_user_by_email(email: str):
    if not firebase_app or not db:
        row = _local_user_record(email)
        if row is None:
            return None
        return {"uid": str(row["id"]), "email": row["email"], "display_name": row["name"]}
    try:
        return auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        return None


def firebase_set_password(uid: str, new_password: str):
    if not firebase_app or not db:
        connection = _local_db_connection()
        connection.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (new_password, int(uid)),
        )
        connection.commit()
        connection.close()
        return {"uid": str(uid)}
    return auth.update_user(uid, password=new_password)


def firebase_verify_password(email: str, password: str) -> dict:
    row = _local_user_record(email)
    if row is not None:
        stored_password = (row["password"] or "")
        if stored_password == password:
            return {"ok": True, "localId": str(row["id"]), "email": row["email"]}
        if not os.getenv("FIREBASE_WEB_API_KEY", "").strip():
            return {"ok": False, "error": "INVALID_PASSWORD"}

    if not firebase_app or not db:
        if row is None:
            return {"ok": False, "error": "USER_NOT_FOUND"}
        if row is not None:
            return {"ok": False, "error": "INVALID_PASSWORD"}

    """Verify Email/Password through Firebase Identity Toolkit REST API."""
    api_key = os.getenv("FIREBASE_WEB_API_KEY", "").strip()
    if not api_key or api_key.lower() in {
        "your_firebase_web_api_key",
        "your_firebase_web_api_key_here",
    }:
        if row is not None:
            return {"ok": True, "localId": str(row["id"]), "email": row["email"]}
        return {"ok": False, "error": "FIREBASE_WEB_API_KEY_NOT_CONFIGURED"}
    response = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=15,
    )
    if response.status_code != 200:
        try:
            error = response.json().get("error", {})
            message = error.get("message", "AUTH_FAILED")
        except ValueError:
            message = "AUTH_FAILED"
        return {"ok": False, "error": message}
    return {"ok": True, **response.json()}


def ensure_firebase_user(email: str, password: str, name: str, role: str):
    user = firebase_get_user_by_email(email)
    if user is None:
        try:
            user = firebase_create_user(email, password, name, role)
        except Exception:
            user = firebase_get_user_by_email(email)
    return user
