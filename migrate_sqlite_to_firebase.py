"""One-time migration helper for the original smart_campus.db.

Usage:
  export FIREBASE_SERVICE_ACCOUNT=/path/serviceAccountKey.json
  export FIREBASE_MIGRATION_PASSWORD='ChangeMe123!'
  python migrate_sqlite_to_firebase.py /path/to/smart_campus.db

Firebase Authentication cannot import Werkzeug password hashes directly through
Admin SDK. Therefore migrated accounts receive the temporary password supplied
in FIREBASE_MIGRATION_PASSWORD and should change it after first login.
"""
from __future__ import annotations
import os
import sqlite3
import sys
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore, auth

COLLECTIONS = [
    "users", "student_profiles", "student_profile_history", "notices", "events",
    "materials", "complaints", "quizzes", "quiz_attempts", "opportunities",
    "attendance", "daily_attendance", "marks", "timetable", "assignments", "attendance_sessions",
    "attendance_scans", "notifications", "audit_logs", "lab_bookings", "lost_found",
]


def init():
    try:
        firebase_admin.get_app()
    except ValueError:
        path = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        if raw:
            import json
            cred = credentials.Certificate(json.loads(raw))
        elif path:
            cred = credentials.Certificate(path)
        else:
            cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
    return firestore.client()


def clean(value):
    try:
        import datetime
        if isinstance(value, (datetime.datetime, datetime.date)):
            return value.isoformat()
    except Exception:
        pass
    return value


def main():
    if len(sys.argv) != 2:
        print("Usage: python migrate_sqlite_to_firebase.py path/to/smart_campus.db")
        raise SystemExit(2)
    db_path = Path(sys.argv[1])
    if not db_path.exists():
        raise SystemExit(f"SQLite database not found: {db_path}")
    temp_password = os.environ.get("FIREBASE_MIGRATION_PASSWORD")
    if not temp_password or len(temp_password) < 6:
        raise SystemExit("Set FIREBASE_MIGRATION_PASSWORD to a password of at least 6 characters.")

    fb = init()
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row

    for table in COLLECTIONS:
        try:
            rows = con.execute(f"SELECT * FROM {table}").fetchall()
        except sqlite3.Error:
            continue
        if not rows:
            continue
        batch = fb.batch()
        count = 0
        for row in rows:
            data = {k: clean(row[k]) for k in row.keys()}
            doc_id = str(data.pop("id"))
            batch.set(fb.collection(table).document(doc_id), data)
            count += 1
            if count == 450:
                batch.commit()
                batch = fb.batch()
                count = 0
        if count:
            batch.commit()
        print(f"Migrated {len(rows)} rows -> {table}")

    # Create corresponding Firebase Auth accounts. Existing accounts are kept.
    try:
        users = con.execute("SELECT id,email,name,role FROM users").fetchall()
        for row in users:
            email = row["email"]
            try:
                user = auth.get_user_by_email(email)
            except auth.UserNotFoundError:
                user = auth.create_user(email=email, password=temp_password, display_name=row["name"])
            auth.set_custom_user_claims(user.uid, {"role": row["role"] or "student"})
        print(f"Processed {len(users)} Firebase Authentication accounts.")
    finally:
        con.close()

    print("Migration complete. Existing SQLite password hashes were not copied to Firebase Authentication.")
    print("All migrated users should sign in with FIREBASE_MIGRATION_PASSWORD and change it in Security.")

if __name__ == "__main__":
    main()
