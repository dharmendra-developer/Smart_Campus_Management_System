from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
import sqlite3
import csv
import io
from datetime import date
import secrets
from urllib.parse import quote_plus
from functools import wraps
from firebase_store import get_db_connection, firebase_create_user, firebase_get_user_by_email, firebase_verify_password, firebase_set_password, ensure_firebase_user


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

app = Flask(__name__)

import os
from dotenv import load_dotenv
load_dotenv()
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")


DEPARTMENTS = [
    "Computer Science & Engineering (CSE)",
    "Information Technology (IT)",
    "Electronics & Communication Engineering (ECE)",
    "Electrical & Electronics Engineering (EE/EEE)",
    "Mechanical Engineering (ME)",
    "Civil Engineering (CIVIL)",
    "Artificial Intelligence & Data Science (AI&DS)",
    "Information Systems (IS)",
]

ALL_DEPARTMENTS = "All Departments"


# ============================================================
# DATABASE CONNECTION
# ============================================================
# Persistent storage is Cloud Firestore. The imported get_db_connection()
# provides an in-memory SQLite compatibility layer for the legacy SQL routes.

# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """
    Create all required database tables and insert demo data.
    """

    connection = get_db_connection()
    cursor = connection.cursor()

    # --------------------------------------------------------
    # Create Tables
    # --------------------------------------------------------

    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            department TEXT NOT NULL DEFAULT 'Computer Science & Engineering (CSE)'
        );

        CREATE TABLE IF NOT EXISTS student_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            phone TEXT,
            enrollment_no TEXT,
            semester TEXT,
            date_of_birth TEXT,
            cgpa TEXT,
            skills TEXT,
            career_interest TEXT,
            linkedin_url TEXT,
            resume_url TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS student_profile_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            department TEXT NOT NULL,
            phone TEXT,
            enrollment_no TEXT,
            semester TEXT,
            date_of_birth TEXT,
            cgpa TEXT,
            skills TEXT,
            career_interest TEXT,
            linkedin_url TEXT,
            resume_url TEXT,
            saved_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            link TEXT,
            youtube_link TEXT,
            department TEXT NOT NULL DEFAULT 'All Departments'
        );

        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            a TEXT NOT NULL,
            b TEXT NOT NULL,
            c TEXT NOT NULL,
            d TEXT NOT NULL,
            answer TEXT NOT NULL,
            department TEXT NOT NULL DEFAULT 'All Departments'
        );

        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            department TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            percentage REAL NOT NULL,
            attempted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            opportunity_type TEXT NOT NULL,
            deadline TEXT,
            link TEXT,
            description TEXT,
            department TEXT NOT NULL DEFAULT 'All Departments',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            attended INTEGER NOT NULL DEFAULT 0,
            total_classes INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (user_id, subject)
        );

        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            assessment TEXT NOT NULL,
            score REAL NOT NULL DEFAULT 0,
            max_score REAL NOT NULL DEFAULT 100,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL,
            day TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            subject TEXT NOT NULL,
            room TEXT
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL,
            subject TEXT NOT NULL,
            session_code TEXT UNIQUE NOT NULL,
            session_date TEXT DEFAULT CURRENT_DATE,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attendance_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            scanned_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (session_id, user_id),
            FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            category TEXT DEFAULT 'Campus',
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            ip_address TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS lab_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lab_name TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            booking_time TEXT NOT NULL,
            purpose TEXT NOT NULL,
            status TEXT DEFAULT 'Requested',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS lost_found (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            status TEXT DEFAULT 'Open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )

    table_columns = {
        table: {
            row[1]
            for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for table in ("users", "materials", "quizzes")
    }

    if "youtube_link" not in table_columns["materials"]:
        cursor.execute(
            "ALTER TABLE materials ADD COLUMN youtube_link TEXT"
        )

    if "department" not in table_columns["users"]:
        cursor.execute(
            """
            ALTER TABLE users
            ADD COLUMN department TEXT NOT NULL DEFAULT 'Computer Science & Engineering (CSE)'
            """
        )

    if "department" not in table_columns["materials"]:
        cursor.execute(
            """
            ALTER TABLE materials
            ADD COLUMN department TEXT NOT NULL DEFAULT 'All Departments'
            """
        )

    if "department" not in table_columns["quizzes"]:
        cursor.execute(
            """
            ALTER TABLE quizzes
            ADD COLUMN department TEXT NOT NULL DEFAULT 'All Departments'
            """
        )

    # Legacy branch migrations can temporarily create duplicate material keys.
    # Rebuild the unique indexes after the data cleanup below.
    cursor.execute("DROP INDEX IF EXISTS uq_materials_subject_department")
    cursor.execute("DROP INDEX IF EXISTS uq_materials_subject_title_department")

    if "branch" in table_columns["users"]:
        cursor.execute("UPDATE users SET department = branch")
    if "branch" in table_columns["materials"]:
        cursor.execute("UPDATE materials SET department = branch")
    if "branch" in table_columns["quizzes"]:
        cursor.execute("UPDATE quizzes SET department = branch")

    cursor.execute(
        "UPDATE materials SET department = ? WHERE department = 'All Branches'",
        (ALL_DEPARTMENTS,),
    )
    cursor.execute(
        "UPDATE quizzes SET department = ? WHERE department = 'All Branches'",
        (ALL_DEPARTMENTS,),
    )

    # --------------------------------------------------------
    # Demo Admin Account
    # --------------------------------------------------------

    admin_exists = cursor.execute(
        "SELECT 1 FROM users WHERE email = ?",
        ("admin@campus.local",),
    ).fetchone()

    if not admin_exists:
        cursor.execute(
            """
            INSERT INTO users (name, email, password, role, department)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Campus Admin",
                "admin@campus.local",
                "admin123",
                "admin",
                ALL_DEPARTMENTS,
            ),
        )

    # --------------------------------------------------------
    # Demo Student Account
    # --------------------------------------------------------

    student_exists = cursor.execute(
        "SELECT 1 FROM users WHERE email = ?",
        ("student@campus.local",),
    ).fetchone()

    if not student_exists:
        cursor.execute(
            """
            INSERT INTO users (name, email, password, role, department)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Demo Student",
                "student@campus.local",
                "student123",
                "student",
                DEPARTMENTS[0],
            ),
        )

    faculty_exists = cursor.execute(
        "SELECT 1 FROM users WHERE email = ?",
        ("faculty@campus.local",),
    ).fetchone()
    if not faculty_exists:
        cursor.execute(
            """
            INSERT INTO users (name, email, password, role, department)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Demo Faculty",
                "faculty@campus.local",
                "faculty123",
                "faculty",
                DEPARTMENTS[0],
            ),
        )

    cursor.execute(
        """
        INSERT OR IGNORE INTO student_profiles (user_id)
        SELECT id FROM users WHERE role = 'student'
        """
    )

    cursor.execute(
        """
        UPDATE users
        SET department = ?
        WHERE email = ? AND (department IS NULL OR department = '')
        """,
        (DEPARTMENTS[0], "student@campus.local"),
    )

    # --------------------------------------------------------
    # Demo Notices
    # --------------------------------------------------------

    notice_count = cursor.execute(
        "SELECT COUNT(*) FROM notices"
    ).fetchone()[0]

    if notice_count == 0:
        notices = [
            (
                "Engineering Day",
                "Project presentation and exhibition will be held "
                "in the seminar hall.",
            ),
            (
                "Exam Notice",
                "Internal assessment schedule will be published soon.",
            ),
        ]

        cursor.executemany(
            """
            INSERT INTO notices (title, content)
            VALUES (?, ?)
            """,
            notices,
        )

    # --------------------------------------------------------
    # Demo Events
    # --------------------------------------------------------

    event_count = cursor.execute(
        "SELECT COUNT(*) FROM events"
    ).fetchone()[0]

    if event_count == 0:
        events = [
            (
                "Engineering Day",
                "2026-09-15",
                "Innovation and project exhibition.",
            ),
            (
                "Coding Workshop",
                "2026-09-20",
                "Hands-on Python and Web Development workshop.",
            ),
        ]

        cursor.executemany(
            """
            INSERT INTO events (title, event_date, description)
            VALUES (?, ?, ?)
            """,
            events,
        )

    opportunity_count = cursor.execute(
        "SELECT COUNT(*) FROM opportunities"
    ).fetchone()[0]

    if opportunity_count == 0:
        cursor.executemany(
            """
            INSERT INTO opportunities
            (title, company, opportunity_type, deadline, link, description, department)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "Python Developer Internship",
                    "Campus Partner Labs",
                    "Internship",
                    "2026-10-15",
                    "#",
                    "Build real-world web features with a guided engineering team.",
                    ALL_DEPARTMENTS,
                ),
                (
                    "Graduate Engineer Trainee",
                    "TechNova Solutions",
                    "Job",
                    "2026-11-01",
                    "#",
                    "An entry-level opportunity for students graduating this academic year.",
                    ALL_DEPARTMENTS,
                ),
            ],
        )

    demo_student_id = cursor.execute(
        "SELECT id FROM users WHERE email = ?",
        ("student@campus.local",),
    ).fetchone()[0]

    attendance_count = cursor.execute(
        "SELECT COUNT(*) FROM attendance WHERE user_id = ?",
        (demo_student_id,),
    ).fetchone()[0]
    if attendance_count == 0:
        cursor.executemany(
            "INSERT INTO attendance (user_id, subject, attended, total_classes) VALUES (?, ?, ?, ?)",
            [
                (demo_student_id, "Computer Networks", 22, 25),
                (demo_student_id, "Python Programming", 24, 26),
                (demo_student_id, "Database Systems", 19, 24),
            ],
        )

    marks_count = cursor.execute(
        "SELECT COUNT(*) FROM marks WHERE user_id = ?",
        (demo_student_id,),
    ).fetchone()[0]
    if marks_count == 0:
        cursor.executemany(
            "INSERT INTO marks (user_id, subject, assessment, score, max_score) VALUES (?, ?, ?, ?, ?)",
            [
                (demo_student_id, "Computer Networks", "Mid Term", 42, 50),
                (demo_student_id, "Python Programming", "Assignment 1", 18, 20),
                (demo_student_id, "Database Systems", "Internal Test", 36, 50),
            ],
        )

    timetable_subjects = {
        DEPARTMENTS[0]: ["Data Structures", "Operating Systems", "Computer Networks", "Database Design", "Software Engineering"],
        DEPARTMENTS[1]: ["Web Technologies", "Cloud Computing", "Network Protocols", "Database Administration", "Systems Analysis"],
        DEPARTMENTS[2]: ["Digital Communication", "Signal Processing", "Microprocessors", "Embedded Systems", "Wireless Networks"],
        DEPARTMENTS[3]: ["Electrical Circuits", "Power Systems", "Digital Electronics", "Control Engineering", "Electrical Machines"],
        DEPARTMENTS[4]: ["Thermodynamics", "Fluid Mechanics", "Machine Design", "Manufacturing Processes", "Engineering Mechanics"],
        DEPARTMENTS[5]: ["Structural Analysis", "Surveying", "Concrete Technology", "Geotechnical Engineering", "Transportation Engineering"],
        DEPARTMENTS[6]: ["Machine Learning", "Data Analytics", "Neural Networks", "Computer Vision", "Data Visualization"],
        DEPARTMENTS[7]: ["Systems Analysis", "Enterprise Systems", "Business Intelligence", "Database Management", "Systems Integration"],
    }
    timetable_rows = []
    timetable_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for department, subjects in timetable_subjects.items():
        existing_slots = cursor.execute(
            "SELECT day, subject FROM timetable WHERE department = ?",
            (department,),
        ).fetchall()
        existing_keys = {(row[0], row[1]) for row in existing_slots}
        for index, subject in enumerate(subjects):
            if (timetable_days[index], subject) not in existing_keys:
                timetable_rows.append(
                    (
                        department,
                        timetable_days[index],
                        "09:00" if index % 2 == 0 else "11:00",
                        "10:00" if index % 2 == 0 else "12:00",
                        subject,
                        f"Room {101 + index}",
                    )
                )

    if timetable_rows:
        cursor.executemany(
            """
            INSERT INTO timetable
            (department, day, start_time, end_time, subject, room)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            timetable_rows,
        )

    assignment_count = cursor.execute(
        "SELECT COUNT(*) FROM assignments"
    ).fetchone()[0]
    if assignment_count == 0:
        cursor.executemany(
            """
            INSERT INTO assignments
            (department, subject, title, due_date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (ALL_DEPARTMENTS, "Python Programming", "Build a Flask mini project", "2026-09-25", "Submit the GitHub link and a short project report."),
                (ALL_DEPARTMENTS, "Database Systems", "Design a campus database", "2026-09-30", "Create an ER diagram and normalized table schema."),
                (DEPARTMENTS[0], "Computer Networks", "Network security presentation", "2026-10-05", "Prepare a five-minute presentation on a security topic."),
            ],
        )

    assignment_subjects = {
        DEPARTMENTS[0]: ["Data Structures", "Operating Systems", "Computer Networks"],
        DEPARTMENTS[1]: ["Web Technologies", "Cloud Computing", "Network Protocols"],
        DEPARTMENTS[2]: ["Digital Communication", "Signal Processing", "Microprocessors"],
        DEPARTMENTS[3]: ["Electrical Circuits", "Power Systems", "Digital Electronics"],
        DEPARTMENTS[4]: ["Thermodynamics", "Fluid Mechanics", "Machine Design"],
        DEPARTMENTS[5]: ["Structural Analysis", "Surveying", "Concrete Technology"],
        DEPARTMENTS[6]: ["Machine Learning", "Data Analytics", "Neural Networks"],
        DEPARTMENTS[7]: ["Systems Analysis", "Enterprise Systems", "Business Intelligence"],
    }
    assignment_rows = []
    for department, subjects in assignment_subjects.items():
        existing_assignments = {
            (row[0], row[1])
            for row in cursor.execute(
                "SELECT subject, title FROM assignments WHERE department = ?",
                (department,),
            ).fetchall()
        }
        for index, subject in enumerate(subjects):
            title = f"{subject} Practical Assignment"
            if (subject, title) not in existing_assignments:
                assignment_rows.append(
                    (
                        department,
                        subject,
                        title,
                        f"2026-{10 + index:02d}-{'15' if index == 0 else '20'}",
                        f"Complete a practical task and submit a short report for {subject.lower()}.",
                    )
                )

    if assignment_rows:
        cursor.executemany(
            """
            INSERT INTO assignments
            (department, subject, title, due_date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            assignment_rows,
        )

    # --------------------------------------------------------
    # Demo Study Materials
    # --------------------------------------------------------

    material_count = cursor.execute(
        "SELECT COUNT(*) FROM materials"
    ).fetchone()[0]

    if material_count == 0:
        materials = [
            (
                "Computer Networks",
                "Unit I Notes",
                "#",
            ),
            (
                "Python",
                "Python Programming Notes",
                "#",
            ),
        ]

        cursor.executemany(
            """
            INSERT INTO materials (subject, title, link)
            VALUES (?, ?, ?)
            """,
            materials,
        )

    department_material_count = cursor.execute(
        "SELECT COUNT(*) FROM materials WHERE department != ?",
        (ALL_DEPARTMENTS,),
    ).fetchone()[0]

    branch_topics = {
        DEPARTMENTS[0]: ["data structures", "operating systems", "computer networks", "database design", "object-oriented programming", "software testing", "web development", "cyber security", "artificial intelligence", "version control"],
        DEPARTMENTS[1]: ["web technologies", "database administration", "network protocols", "cloud computing", "information security", "systems analysis", "mobile applications", "data management", "IT service management", "software deployment"],
        DEPARTMENTS[2]: ["digital communication", "signal processing", "microprocessors", "antenna systems", "embedded systems", "wireless networks", "fiber optics", "control systems", "image processing", "semiconductor devices"],
        DEPARTMENTS[3]: ["electrical circuits", "power generation", "digital electronics", "transformers", "control engineering", "power transmission", "electrical machines", "renewable energy", "high voltage engineering", "power system protection"],
        DEPARTMENTS[4]: ["thermodynamics", "fluid mechanics", "machine design", "manufacturing processes", "heat transfer", "engineering mechanics", "automobile engineering", "CAD modelling", "industrial engineering", "material science"],
        DEPARTMENTS[5]: ["structural analysis", "surveying", "concrete technology", "geotechnical engineering", "transportation engineering", "hydraulics", "environmental engineering", "building planning", "construction management", "water resources"],
        DEPARTMENTS[6]: ["machine learning", "data analytics", "neural networks", "natural language processing", "computer vision", "probability for data science", "deep learning", "data visualization", "feature engineering", "responsible AI"],
        DEPARTMENTS[7]: ["information systems analysis", "enterprise systems", "systems design", "business intelligence", "database management", "IT governance", "requirements engineering", "information security", "data modelling", "systems integration"],
    }

    for department in DEPARTMENTS:
        cursor.execute(
            """
            UPDATE materials
            SET department = ?
            WHERE department = ?
              AND (title LIKE ? OR title LIKE ?)
            """,
            (
                department,
                ALL_DEPARTMENTS,
                f"% - {department} Notes",
                f"% - {department} Study Material",
            ),
        )

    cursor.execute(
        """
        DELETE FROM materials
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM materials
            GROUP BY subject, title, department
        )
        """
    )

    cursor.execute(
        """
        DELETE FROM materials
        WHERE department != ?
        AND id NOT IN (
        SELECT MAX(id)
        FROM materials
        WHERE department != ?
        GROUP BY department, subject
        )
        """,
        (ALL_DEPARTMENTS, ALL_DEPARTMENTS),
    )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_materials_subject_title_department
        ON materials (subject, title, department)
        """
    )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_materials_subject_department
        ON materials (subject, department)
        """
    )

    branch_materials = []
    for department, topics in branch_topics.items():
        existing_subjects = {
            row[0]
            for row in cursor.execute(
                "SELECT subject FROM materials WHERE department = ?",
                (department,),
            ).fetchall()
        }
        for topic in topics[:10]:
            subject = topic.title()
            if subject not in existing_subjects:
                wikipedia_link = f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_').title()}"
                youtube_link = f"https://www.youtube.com/results?search_query={quote_plus(topic + ' tutorial')}"
                branch_materials.append(
                    (
                        department,
                        subject,
                        f"{subject} - {department} Study Material",
                                wikipedia_link,
                                youtube_link,
                    )
                )

    if branch_materials:
        cursor.executemany(
            """
            INSERT INTO materials
            (department, subject, title, link, youtube_link)
            VALUES (?, ?, ?, ?, ?)
            """,
            branch_materials,
        )

    cursor.execute(
        """
        UPDATE materials
        SET link = CASE
                WHEN link IS NULL OR link = '#' THEN
                    'https://en.wikipedia.org/wiki/' || replace(subject, ' ', '_')
                ELSE link
            END,
            youtube_link = CASE
                WHEN youtube_link IS NULL OR youtube_link = '' THEN
                    'https://www.youtube.com/results?search_query=' || replace(subject, ' ', '+') || '+tutorial'
                ELSE youtube_link
            END
        """
    )

    branch_questions = []
    for department, topics in branch_topics.items():
        existing_count = cursor.execute(
            "SELECT COUNT(*) FROM quizzes WHERE department = ?",
            (department,),
        ).fetchone()[0]
        existing_answers = {
            row[0]
            for row in cursor.execute(
                "SELECT a FROM quizzes WHERE department = ?",
                (department,),
            ).fetchall()
        }
        for topic in topics:
            if existing_count + len([item for item in branch_questions if item[-1] == department]) >= 10:
                break
            if topic.title() not in existing_answers:
                branch_questions.append(
                    (
                        f"How is {topic} related to {department}?",
                        topic.title(),
                        "Fashion Design",
                        "Hotel Management",
                        "Fine Arts",
                        "a",
                        department,
                    )
                )

    if branch_questions:
        cursor.executemany(
            """
            INSERT INTO quizzes
            (question, a, b, c, d, answer, department)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            branch_questions,
        )
        questions = [
            (
                "Which language is used in this project?",
                "Java",
                "Python",
                "C++",
                "PHP",
                "b",
                ALL_DEPARTMENTS,
            ),
            (
                "Flask is a ____ framework.",
                "Python web",
                "Database",
                "OS",
                "CSS",
                "a",
                ALL_DEPARTMENTS,
            ),
            (
                "Which database is used by default?",
                "MongoDB",
                "Oracle",
                "Cloud Firestore",
                "Redis",
                "c",
                ALL_DEPARTMENTS,
            ),
            (
                "HTML is used for?",
                "Styling",
                "Structure",
                "Database",
                "Authentication",
                "b",
                ALL_DEPARTMENTS,
            ),
            (
                "CSS is mainly used for?",
                "Styling",
                "Queries",
                "Routing",
                "Hashing",
                "a",
                ALL_DEPARTMENTS,
            ),
        ]

        cursor.executemany(
            """
            INSERT INTO quizzes
            (question, a, b, c, d, answer, department)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            questions,
        )

    department_quiz_count = cursor.execute(
        "SELECT COUNT(*) FROM quizzes WHERE department != ?",
        (ALL_DEPARTMENTS,),
    ).fetchone()[0]

    if department_quiz_count == 0:
        cursor.executemany(
            """
            INSERT INTO quizzes
            (question, a, b, c, d, answer, department)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"Which area is most closely related to {department}?",
                    department,
                    "Fashion Design",
                    "Hotel Management",
                    "Fine Arts",
                    "a",
                    department,
                )
                for department in DEPARTMENTS
            ],
        )

    connection.commit()
    connection.close()

    ensure_firebase_user("admin@campus.local", "admin123", "Campus Admin", "admin")
    ensure_firebase_user("student@campus.local", "student123", "Demo Student", "student")
    ensure_firebase_user("faculty@campus.local", "faculty123", "Demo Faculty", "faculty")


# ============================================================
# AUTHENTICATION DECORATOR
# ============================================================

def login_required(function):
    """
    Allow access only to logged-in users.
    """

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def log_action(user_id, action):
    connection = get_db_connection()
    connection.execute(
        "INSERT INTO audit_logs (user_id, action, ip_address) VALUES (?, ?, ?)",
        (user_id, action, request.remote_addr),
    )
    connection.commit()
    connection.close()


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def index():

    connection = get_db_connection()

    notices = connection.execute(
        """
        SELECT *
        FROM notices
        ORDER BY id DESC
        LIMIT 5
        """
    ).fetchall()

    events = connection.execute(
        """
        SELECT *
        FROM events
        ORDER BY event_date
        LIMIT 5
        """
    ).fetchall()

    connection.close()

    return render_template(
        "index.html",
        notices=notices,
        events=events,
    )


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        department = request.form.get("department", "").strip()

        # Basic validation
        if not name or not email or not password or department not in DEPARTMENTS:
            flash("All fields are required.", "danger")
            return render_template("register.html", departments=DEPARTMENTS)

        if len(password) < 6:
            flash(
                "Password must contain at least 6 characters.",
                "danger",
            )
            return render_template("register.html", departments=DEPARTMENTS)

        connection = get_db_connection()

        try:
            if firebase_get_user_by_email(email):
                raise sqlite3.IntegrityError("Email already registered")
            firebase_create_user(email, password, name, "student")
            connection.execute(
                """
                INSERT INTO users (name, email, password, department)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, password, department),
            )
            connection.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.", "danger")
        except Exception as exc:
            flash(f"Firebase registration failed: {exc}", "danger")
        finally:
            connection.close()

    return render_template("register.html", departments=DEPARTMENTS)


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            "",
        ).strip().lower()

        password = request.form.get(
            "password",
            "",
        )

        connection = get_db_connection()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

        connection.close()

        auth_result = firebase_verify_password(email, password)
        if user and auth_result.get("ok"):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            session["department"] = user["department"]
            session["firebase_uid"] = auth_result.get("localId")
            log_action(user["id"], "login")
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard"))

        auth_error = auth_result.get("error", "AUTH_FAILED")
        if auth_error in {"FIREBASE_WEB_API_KEY_NOT_CONFIGURED", "API_KEY_INVALID"}:
            flash(
                "Login setup incomplete: add the Firebase Web API key to .env, "
                "then restart the app.",
                "danger",
            )
        elif auth_error == "OPERATION_NOT_ALLOWED":
            flash(
                "Firebase Email/Password sign-in is disabled. Enable it in "
                "Firebase Console > Authentication > Sign-in method.",
                "danger",
            )
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out successfully.",
        "success",
    )

    return redirect(url_for("index"))


# ============================================================
# STUDENT PROFILE
# ============================================================

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():

    connection = get_db_connection()

    user = connection.execute(
        """
        SELECT id, name, email, role, department
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],),
    ).fetchone()

    profile_data = connection.execute(
        "SELECT * FROM student_profiles WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()

    if not user:
        connection.close()
        session.clear()
        flash("Your account could not be found.", "danger")
        return redirect(url_for("login"))

    profile_departments = DEPARTMENTS
    if user["role"] == "admin":
        profile_departments = DEPARTMENTS + [ALL_DEPARTMENTS]

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        department = request.form.get("department", "").strip()
        profile_fields = (
            request.form.get("phone", "").strip(),
            request.form.get("enrollment_no", "").strip(),
            request.form.get("semester", "").strip(),
            request.form.get("date_of_birth", "").strip(),
            request.form.get("cgpa", "").strip(),
            request.form.get("skills", "").strip(),
            request.form.get("career_interest", "").strip(),
            request.form.get("linkedin_url", "").strip(),
            request.form.get("resume_url", "").strip(),
        )

        if not name or not email or department not in profile_departments:
            connection.close()
            flash("Name, email and a valid department are required.", "danger")
            return render_template(
                "profile.html",
                user=user,
                profile=profile_data,
                departments=profile_departments,
            )

        existing_user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = ? AND id != ?
            """,
            (email, session["user_id"]),
        ).fetchone()

        if existing_user:
            connection.close()
            flash("That email is already registered.", "danger")
            return render_template(
                "profile.html",
                user=user,
                departments=profile_departments,
            )

        connection.execute(
            """
            INSERT INTO student_profile_history
            (user_id, name, email, department, phone, enrollment_no, semester,
             date_of_birth, cgpa, skills, career_interest, linkedin_url, resume_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                user["name"],
                user["email"],
                user["department"],
                profile_data["phone"] if profile_data else "",
                profile_data["enrollment_no"] if profile_data else "",
                profile_data["semester"] if profile_data else "",
                profile_data["date_of_birth"] if profile_data else "",
                profile_data["cgpa"] if profile_data else "",
                profile_data["skills"] if profile_data else "",
                profile_data["career_interest"] if profile_data else "",
                profile_data["linkedin_url"] if profile_data else "",
                profile_data["resume_url"] if profile_data else "",
            ),
        )

        connection.execute(
            """
            UPDATE users
            SET name = ?, email = ?, department = ?
            WHERE id = ?
            """,
            (name, email, department, session["user_id"]),
        )

        connection.execute(
            """
            INSERT INTO student_profiles
                (user_id, phone, enrollment_no, semester, date_of_birth, cgpa,
                 skills, career_interest, linkedin_url, resume_url, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                phone = excluded.phone,
                enrollment_no = excluded.enrollment_no,
                semester = excluded.semester,
                date_of_birth = excluded.date_of_birth,
                cgpa = excluded.cgpa,
                skills = excluded.skills,
                career_interest = excluded.career_interest,
                linkedin_url = excluded.linkedin_url,
                resume_url = excluded.resume_url,
                updated_at = CURRENT_TIMESTAMP
            """,
            (session["user_id"], *profile_fields),
        )
        connection.commit()
        connection.close()

        session["name"] = name
        session["department"] = department
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))

    connection.close()
    return render_template(
        "profile.html",
        user=user,
        profile=profile_data,
        departments=profile_departments,
    )


# ============================================================
# STUDENT DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    connection = get_db_connection()

    notices = connection.execute(
        """
        SELECT *
        FROM notices
        ORDER BY id DESC
        LIMIT 5
        """
    ).fetchall()

    events = connection.execute(
        """
        SELECT *
        FROM events
        ORDER BY event_date
        LIMIT 5
        """
    ).fetchall()

    complaints = connection.execute(
        """
        SELECT *
        FROM complaints
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],),
    ).fetchall()

    profile = connection.execute(
        "SELECT * FROM student_profiles WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()

    opportunities = connection.execute(
        """
        SELECT * FROM opportunities
        WHERE department = ? OR department = ?
        ORDER BY deadline IS NULL, deadline
        LIMIT 5
        """,
        (session.get("department", DEPARTMENTS[0]), ALL_DEPARTMENTS),
    ).fetchall()

    connection.close()

    return render_template(
        "dashboard.html",
        notices=notices,
        events=events,
        complaints=complaints,
        profile=profile,
        opportunities=opportunities,
    )


# ============================================================
# FACULTY PORTAL
# ============================================================

@app.route("/faculty")
@login_required
def faculty_portal():
    if session.get("role") not in {"faculty", "admin"}:
        return "Access denied", 403
    connection = get_db_connection()
    students = connection.execute(
        """
        SELECT users.id, users.name, users.email, users.department,
               student_profiles.semester, student_profiles.cgpa
        FROM users
        LEFT JOIN student_profiles ON student_profiles.user_id = users.id
        WHERE users.role = 'student' AND users.department = ?
        ORDER BY users.name
        """,
        (session.get("department", DEPARTMENTS[0]),),
    ).fetchall()
    recent_marks = connection.execute(
        """
        SELECT marks.*, users.name
        FROM marks JOIN users ON users.id = marks.user_id
        WHERE users.department = ?
        ORDER BY marks.id DESC LIMIT 12
        """,
        (session.get("department", DEPARTMENTS[0]),),
    ).fetchall()
    attendance_summary = connection.execute(
        """
        SELECT users.name, attendance.subject, attendance.attended, attendance.total_classes
        FROM attendance JOIN users ON users.id = attendance.user_id
        WHERE users.department = ?
        ORDER BY users.name, attendance.subject
        """,
        (session.get("department", DEPARTMENTS[0]),),
    ).fetchall()
    attendance_date = request.args.get("attendance_date", date.today().isoformat())
    selected_subject = request.args.get("attendance_subject", "").strip()
    daily_statuses = {}
    if selected_subject:
        daily_rows = connection.execute(
            """
            SELECT daily_attendance.user_id, daily_attendance.status
            FROM daily_attendance
            JOIN users ON users.id = daily_attendance.user_id
            WHERE users.department = ? AND daily_attendance.subject = ?
              AND daily_attendance.attendance_date = ?
            """,
            (session.get("department", DEPARTMENTS[0]), selected_subject, attendance_date),
        ).fetchall()
        daily_statuses = {row["user_id"]: row["status"] for row in daily_rows}
    connection.close()
    return render_template(
        "faculty.html",
        students=students,
        recent_marks=recent_marks,
        attendance_summary=attendance_summary,
        attendance_date=attendance_date,
        selected_subject=selected_subject,
        daily_statuses=daily_statuses,
    )


@app.post("/faculty/marks")
@login_required
def add_faculty_mark():
    if session.get("role") not in {"faculty", "admin"}:
        return "Access denied", 403
    connection = get_db_connection()
    student_id = request.form.get("student_id", type=int)
    subject = request.form.get("subject", "").strip()
    assessment = request.form.get("assessment", "").strip()
    score = request.form.get("score", type=float)
    max_score = request.form.get("max_score", type=float)
    student = connection.execute("SELECT id FROM users WHERE id = ? AND role = 'student'", (student_id,)).fetchone()
    if not student or not subject or not assessment or score is None or not max_score or score < 0 or score > max_score:
        connection.close()
        flash("Enter valid student and marks details.", "danger")
        return redirect(url_for("faculty_portal"))
    connection.execute("INSERT INTO marks (user_id, subject, assessment, score, max_score) VALUES (?, ?, ?, ?, ?)", (student_id, subject, assessment, score, max_score))
    connection.execute("INSERT INTO notifications (user_id, title, message, category) VALUES (?, ?, ?, ?)", (student_id, "New marks published", f"{assessment} marks for {subject} are now available.", "Academic"))
    connection.commit()
    connection.close()
    log_action(session["user_id"], f"added marks for student {student_id}")
    flash("Marks saved and student notified.", "success")
    return redirect(url_for("faculty_portal"))


@app.post("/faculty/attendance")
@login_required
def add_faculty_attendance():
    if session.get("role") not in {"faculty", "admin"}:
        return "Access denied", 403
    student_id = request.form.get("student_id", type=int)
    subject = request.form.get("subject", "").strip()
    attended = request.form.get("attended", type=int)
    total_classes = request.form.get("total_classes", type=int)
    connection = get_db_connection()
    valid_student = connection.execute("SELECT id FROM users WHERE id = ? AND role = 'student'", (student_id,)).fetchone()
    if not valid_student or not subject or attended is None or total_classes is None or attended < 0 or total_classes <= 0 or attended > total_classes:
        connection.close()
        flash("Enter valid attendance details.", "danger")
        return redirect(url_for("faculty_portal"))
    connection.execute("INSERT INTO attendance (user_id, subject, attended, total_classes) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, subject) DO UPDATE SET attended = excluded.attended, total_classes = excluded.total_classes", (student_id, subject, attended, total_classes))
    connection.execute("INSERT INTO notifications (user_id, title, message, category) VALUES (?, ?, ?, ?)", (student_id, "Attendance updated", f"{subject} attendance is now {attended}/{total_classes}.", "Academic"))
    connection.commit()
    connection.close()
    log_action(session["user_id"], f"updated attendance for student {student_id}")
    flash("Attendance saved and student notified.", "success")
    return redirect(url_for("faculty_portal"))


@app.post("/faculty/attendance/daily")
@login_required
def save_daily_attendance():
    if session.get("role") not in {"faculty", "admin"}:
        return "Access denied", 403

    subject = request.form.get("daily_subject", "").strip()
    attendance_date = request.form.get("attendance_date", "").strip()
    department = session.get("department", DEPARTMENTS[0])
    try:
        date.fromisoformat(attendance_date)
    except ValueError:
        attendance_date = ""

    connection = get_db_connection()
    students = connection.execute(
        "SELECT id FROM users WHERE role = 'student' AND department = ? ORDER BY name",
        (department,),
    ).fetchall()
    valid_statuses = {"present", "absent"}
    statuses = {
        student["id"]: request.form.get(f"attendance_{student['id']}", "").strip().lower()
        for student in students
    }
    if not subject or not attendance_date or not students or set(statuses.values()) - valid_statuses:
        connection.close()
        flash("Select a valid date, subject and attendance status for every student.", "danger")
        return redirect(url_for("faculty_portal"))

    for student in students:
        student_id = student["id"]
        connection.execute(
            """
            INSERT INTO daily_attendance (user_id, subject, attendance_date, status, marked_by)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, subject, attendance_date) DO UPDATE SET
                status = excluded.status, marked_by = excluded.marked_by
            """,
            (student_id, subject, attendance_date, statuses[student_id], session["user_id"]),
        )
        totals = connection.execute(
            """
            SELECT COUNT(*) AS total_classes,
                   SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) AS attended
            FROM daily_attendance
            WHERE user_id = ? AND subject = ?
            """,
            (student_id, subject),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO attendance (user_id, subject, attended, total_classes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, subject) DO UPDATE SET
                attended = excluded.attended, total_classes = excluded.total_classes
            """,
            (student_id, subject, totals["attended"] or 0, totals["total_classes"] or 0),
        )
        connection.execute(
            """
            INSERT INTO notifications (user_id, title, message, category)
            VALUES (?, ?, ?, ?)
            """,
            (student_id, "Daily attendance updated", f"{subject} attendance marked for {attendance_date}.", "Academic"),
        )
    connection.commit()
    connection.close()
    log_action(session["user_id"], f"marked daily attendance for {subject} on {attendance_date}")
    flash(f"Daily attendance saved for {len(students)} students.", "success")
    return redirect(url_for("faculty_portal", attendance_date=attendance_date, attendance_subject=subject))


@app.post("/faculty/assignment")
@login_required
def add_faculty_assignment():
    if session.get("role") not in {"faculty", "admin"}:
        return "Access denied", 403
    subject = request.form.get("subject", "").strip()
    title = request.form.get("title", "").strip()
    due_date = request.form.get("due_date", "").strip()
    description = request.form.get("description", "").strip()
    if not subject or not title or not due_date:
        flash("Subject, title and due date are required.", "danger")
        return redirect(url_for("faculty_portal"))
    connection = get_db_connection()
    connection.execute("INSERT INTO assignments (department, subject, title, due_date, description) VALUES (?, ?, ?, ?, ?)", (session.get("department", DEPARTMENTS[0]), subject, title, due_date, description))
    connection.execute("INSERT INTO notifications (user_id, title, message, category) SELECT id, ?, ?, ? FROM users WHERE department = ? AND role = 'student'", ("New assignment", f"{title} is due on {due_date}.", "Academic", session.get("department", DEPARTMENTS[0])))
    connection.commit()
    connection.close()
    log_action(session["user_id"], "created a faculty assignment")
    flash("Assignment created and students notified.", "success")
    return redirect(url_for("faculty_portal"))


# ============================================================
# CAMPUS SERVICES
# ============================================================

@app.route("/services")
@login_required
def campus_services():
    services = [
        {"title": "Library Desk", "icon": "▣", "detail": "Check book availability and contact the library desk.", "action": "library@smartcampus.local"},
        {"title": "Transport", "icon": "↗", "detail": "Campus shuttle leaves Main Gate at 08:00 and 16:30.", "action": "Transport schedule"},
        {"title": "Emergency Support", "icon": "!", "detail": "For urgent campus support, contact the help desk.", "action": "+92 111 222 333"},
        {"title": "Lost & Found", "icon": "⌂", "detail": "Report or find an item through the student help desk.", "action": "Open help desk"},
        {"title": "Lab Booking", "icon": "◫", "detail": "Request a lab slot from your department coordinator.", "action": "Faculty coordinator"},
        {"title": "Scholarships", "icon": "★", "detail": "Visit Student Affairs for current scholarship guidance.", "action": "Student Affairs"},
    ]
    connection = get_db_connection()
    bookings = connection.execute("SELECT * FROM lab_bookings WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (session["user_id"],)).fetchall()
    lost_items = connection.execute("SELECT * FROM lost_found WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (session["user_id"],)).fetchall()
    connection.close()
    return render_template("services.html", services=services, bookings=bookings, lost_items=lost_items)


@app.post("/services/lab-booking")
@login_required
def book_lab():
    lab_name = request.form.get("lab_name", "").strip()
    booking_date = request.form.get("booking_date", "").strip()
    booking_time = request.form.get("booking_time", "").strip()
    purpose = request.form.get("purpose", "").strip()
    if not lab_name or not booking_date or not booking_time or not purpose:
        flash("All lab booking fields are required.", "danger")
        return redirect(url_for("campus_services"))
    connection = get_db_connection()
    connection.execute("INSERT INTO lab_bookings (user_id, lab_name, booking_date, booking_time, purpose) VALUES (?, ?, ?, ?, ?)", (session["user_id"], lab_name, booking_date, booking_time, purpose))
    connection.commit()
    connection.close()
    flash("Lab booking request submitted.", "success")
    return redirect(url_for("campus_services"))


@app.post("/services/lost-found")
@login_required
def report_lost_found():
    item_type = request.form.get("item_type", "Lost").strip()
    item_name = request.form.get("item_name", "").strip()
    description = request.form.get("description", "").strip()
    location = request.form.get("location", "").strip()
    if not item_name or not description or not location:
        flash("Item name, description and location are required.", "danger")
        return redirect(url_for("campus_services"))
    connection = get_db_connection()
    connection.execute("INSERT INTO lost_found (user_id, item_type, item_name, description, location) VALUES (?, ?, ?, ?, ?)", (session["user_id"], item_type, item_name, description, location))
    connection.commit()
    connection.close()
    flash("Lost and found report submitted.", "success")
    return redirect(url_for("campus_services"))


# ============================================================
# RESUME BUILDER
# ============================================================

@app.route("/resume")
@login_required
def resume():
    connection = get_db_connection()
    profile = connection.execute("SELECT users.*, student_profiles.* FROM users LEFT JOIN student_profiles ON student_profiles.user_id = users.id WHERE users.id = ?", (session["user_id"],)).fetchone()
    marks = connection.execute("SELECT subject, score, max_score FROM marks WHERE user_id = ? ORDER BY id DESC LIMIT 5", (session["user_id"],)).fetchall()
    connection.close()
    fields = [profile["phone"], profile["enrollment_no"], profile["semester"], profile["cgpa"], profile["skills"], profile["career_interest"], profile["linkedin_url"], profile["resume_url"]] if profile else []
    completeness = round(sum(bool(value) for value in fields) / len(fields) * 100) if fields else 0
    return render_template("resume.html", profile=profile, marks=marks, completeness=completeness)


@app.route("/resume/download")
@login_required
def resume_download():
    connection = get_db_connection()
    profile = connection.execute("SELECT users.*, student_profiles.* FROM users LEFT JOIN student_profiles ON student_profiles.user_id = users.id WHERE users.id = ?", (session["user_id"],)).fetchone()
    connection.close()
    sections = [
        ("ACADEMIC PROFILE", [f"Enrollment: {profile['enrollment_no'] or 'Not added'}", f"Semester: {profile['semester'] or 'Not added'}", f"CGPA: {profile['cgpa'] or 'Not added'}"]),
        ("SKILLS", [profile["skills"] or "Add your skills in Profile"]),
        ("CAREER INTEREST", [profile["career_interest"] or "Not added"]),
        ("LINKS", [profile["linkedin_url"] or "LinkedIn not added", profile["resume_url"] or "Resume link not added"]),
    ]
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buffer = io.BytesIO()
        document = canvas.Canvas(buffer, pagesize=A4)
        document.setTitle("Smart Campus Resume")
        document.setFont("Helvetica-Bold", 22)
        document.drawString(56, 780, profile["name"])
        document.setFont("Helvetica", 10)
        document.drawString(56, 762, f"{profile['email']} | {profile['department']}")
        y = 720
        for heading, lines in sections:
            document.setFont("Helvetica-Bold", 12)
            document.drawString(56, y, heading)
            y -= 20
            document.setFont("Helvetica", 10)
            for line in lines:
                document.drawString(70, y, line[:110])
                y -= 16
            y -= 12
        document.save()
        buffer.seek(0)
        content = buffer.getvalue()
    except ModuleNotFoundError:
        # Minimal PDF fallback keeps resume download functional in lean deployments.
        lines = [profile["name"], f"{profile['email']} | {profile['department']}" ]
        lines.extend(line for heading, values in sections for line in [heading, *values])
        commands = ["BT /F1 16 Tf 56 780 Td (%s) Tj" % profile["name"].replace("(", "[").replace(")", "]")]
        for line in lines[1:]:
            safe_line = line.replace("(", "[").replace(")", "]")[:110]
            commands.append("0 -20 Td /F1 10 Tf (%s) Tj" % safe_line)
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", "replace")
        objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>", b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>", b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
        content = b"%PDF-1.4\n"
        offsets = [0]
        for index, obj in enumerate(objects, 1):
            offsets.append(len(content))
            content += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
        xref = len(content)
        content += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
        content += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
        content += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return app.response_class(content, mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=smart-campus-resume.pdf"})


# ============================================================
# SECURITY AND ADMIN REPORTS
# ============================================================

@app.route("/security", methods=["GET", "POST"])
@login_required
def security():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        connection = get_db_connection()
        user = connection.execute("SELECT email FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if not user or len(new_password) < 6:
            connection.close()
            flash("Current password is incorrect or new password is too short.", "danger")
        else:
            verification = firebase_verify_password(user["email"], current_password)
            if not verification.get("ok"):
                connection.close()
                flash("Current password is incorrect or new password is too short.", "danger")
            else:
                firebase_set_password(verification["localId"], new_password)
                connection.close()
                log_action(session["user_id"], "password changed")
                flash("Password changed successfully.", "success")
    return render_template("security.html")


@app.route("/admin/report/students.csv")
@login_required
def student_report():
    if session.get("role") != "admin":
        return "Access denied", 403
    connection = get_db_connection()
    rows = connection.execute("SELECT id, name, email, department, role FROM users ORDER BY department, name").fetchall()
    connection.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Email", "Department", "Role"])
    writer.writerows([[row["id"], row["name"], row["email"], row["department"], row["role"]] for row in rows])
    return app.response_class(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=smart-campus-students.csv"})


# ============================================================
# NOTIFICATION CENTER
# ============================================================

@app.route("/notifications")
@login_required
def notifications():
    connection = get_db_connection()
    rows = connection.execute(
        """
        SELECT * FROM notifications
        WHERE user_id IS NULL OR user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 30
        """,
        (session["user_id"],),
    ).fetchall()
    connection.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ?",
        (session["user_id"],),
    )
    connection.commit()
    connection.close()
    return render_template("notifications.html", notifications=rows)


# ============================================================
# QR ATTENDANCE
# ============================================================

@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance_portal():
    connection = get_db_connection()
    message = None
    if request.method == "POST":
        session_code = request.form.get("session_code", "").strip().upper()
        attendance_session = connection.execute(
            """
            SELECT * FROM attendance_sessions
            WHERE session_code = ? AND department = ? AND active = 1
            """,
            (session_code, session.get("department", DEPARTMENTS[0])),
        ).fetchone()
        if not attendance_session:
            flash("Invalid or closed attendance code.", "danger")
        else:
            try:
                connection.execute(
                    "INSERT INTO attendance_scans (session_id, user_id) VALUES (?, ?)",
                    (attendance_session["id"], session["user_id"]),
                )
                connection.commit()
                flash(f"Attendance marked for {attendance_session['subject']}.", "success")
            except sqlite3.IntegrityError:
                flash("You have already marked attendance for this session.", "info")

    active_sessions = connection.execute(
        """
        SELECT * FROM attendance_sessions
        WHERE department = ? AND active = 1
        ORDER BY id DESC
        """,
        (session.get("department", DEPARTMENTS[0]),),
    ).fetchall()
    connection.close()
    return render_template("attendance.html", active_sessions=active_sessions)


@app.post("/admin/attendance/session")
@login_required
def create_attendance_session():
    if session.get("role") != "admin":
        return "Access denied", 403
    subject = request.form.get("subject", "").strip()
    department = request.form.get("department", "").strip()
    session_code = request.form.get("session_code", "").strip().upper()
    if not subject or department not in DEPARTMENTS:
        flash("Subject and a valid department are required.", "danger")
        return redirect(url_for("admin"))
    connection = get_db_connection()
    if session_code and len(session_code) < 4:
        connection.close()
        flash("Custom session code must contain at least 4 characters.", "danger")
        return redirect(url_for("admin"))
    if not session_code:
        subject_code = "".join(character for character in subject.upper() if character.isalnum())[:6] or "CLASS"
        while True:
            session_code = f"{subject_code}-{date.today().strftime('%d%m')}-{secrets.token_hex(2).upper()}"
            exists = connection.execute(
                "SELECT 1 FROM attendance_sessions WHERE session_code = ?",
                (session_code,),
            ).fetchone()
            if not exists:
                break
    try:
        connection.execute(
            "INSERT INTO attendance_sessions (department, subject, session_code) VALUES (?, ?, ?)",
            (department, subject, session_code),
        )
    except sqlite3.IntegrityError:
        connection.close()
        flash("This session code already exists. Leave the code blank to generate a new one.", "danger")
        return redirect(url_for("admin"))
    connection.execute(
        "INSERT INTO notifications (user_id, title, message, category) SELECT id, ?, ?, ? FROM users WHERE department = ? AND role = 'student'",
        ("New attendance session", f"{subject} attendance is open. Code: {session_code}", "Attendance", department),
    )
    connection.commit()
    connection.close()
    flash("Attendance session created and students notified.", "success")
    return redirect(url_for("admin"))


# ============================================================
# PLACEMENT ELIGIBILITY
# ============================================================

@app.route("/placement")
@login_required
def placement():
    connection = get_db_connection()
    user_id = session["user_id"]
    profile = connection.execute("SELECT * FROM student_profiles WHERE user_id = ?", (user_id,)).fetchone()
    attendance = connection.execute("SELECT attended, total_classes FROM attendance WHERE user_id = ?", (user_id,)).fetchall()
    opportunities = connection.execute(
        "SELECT * FROM opportunities WHERE department = ? OR department = ? ORDER BY deadline IS NULL, deadline",
        (session.get("department", DEPARTMENTS[0]), ALL_DEPARTMENTS),
    ).fetchall()
    connection.close()
    attendance_average = round(sum(row["attended"] / row["total_classes"] * 100 for row in attendance if row["total_classes"]) / len([row for row in attendance if row["total_classes"]]), 1) if attendance else 0
    try:
        cgpa = float((profile["cgpa"] or "0").split()[0]) if profile else 0
    except ValueError:
        cgpa = 0
    checks = [
        {"label": "Minimum CGPA 6.0", "passed": cgpa >= 6},
        {"label": "Attendance at least 75%", "passed": attendance_average >= 75},
        {"label": "Skills added to profile", "passed": bool(profile and profile["skills"])},
    ]
    return render_template("placement.html", profile=profile, attendance_average=attendance_average, checks=checks, opportunities=opportunities)


# ============================================================
# STUDY MATERIALS
# ============================================================

@app.route("/materials")
@login_required
def materials():

    connection = get_db_connection()

    materials = connection.execute(
        """
        SELECT *
        FROM materials
        WHERE department = ? OR department = ?
        ORDER BY subject, title
        """
        ,
        (session.get("department", DEPARTMENTS[0]), ALL_DEPARTMENTS),
    ).fetchall()

    connection.close()

    return render_template(
        "materials.html",
        materials=materials,
        department=session.get("department", DEPARTMENTS[0]),
    )


# ============================================================
# ACADEMIC HUB
# ============================================================

@app.route("/academics")
@login_required
def academics():
    connection = get_db_connection()
    user_id = session["user_id"]
    department = session.get("department", DEPARTMENTS[0])

    attendance = connection.execute(
        "SELECT * FROM attendance WHERE user_id = ? ORDER BY subject",
        (user_id,),
    ).fetchall()
    marks = connection.execute(
        """
        SELECT * FROM marks
        WHERE user_id = ?
        ORDER BY subject, id DESC
        """,
        (user_id,),
    ).fetchall()
    timetable = connection.execute(
        """
        SELECT * FROM timetable
        WHERE department = ? OR department = ?
        ORDER BY CASE day
            WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 ELSE 7 END,
            start_time
        """,
        (department, ALL_DEPARTMENTS),
    ).fetchall()
    assignments = connection.execute(
        """
        SELECT * FROM assignments
        WHERE department = ? OR department = ?
        ORDER BY due_date
        """,
        (department, ALL_DEPARTMENTS),
    ).fetchall()
    connection.close()

    attendance_average = round(
        sum((row["attended"] / row["total_classes"]) * 100 for row in attendance if row["total_classes"])
        / len([row for row in attendance if row["total_classes"]]),
        1,
    ) if attendance else 0

    return render_template(
        "academics.html",
        attendance=attendance,
        attendance_average=attendance_average,
        marks=marks,
        timetable=timetable,
        assignments=assignments,
        chart_labels=[row["subject"] for row in attendance],
        chart_attendance=[round((row["attended"] / row["total_classes"]) * 100, 1) if row["total_classes"] else 0 for row in attendance],
        chart_mark_labels=[row["subject"] for row in marks],
        chart_marks=[round((row["score"] / row["max_score"]) * 100, 1) if row["max_score"] else 0 for row in marks],
    )


# ============================================================
# SMART STUDENT INSIGHTS
# ============================================================

@app.route("/insights")
@login_required
def insights():
    connection = get_db_connection()
    user_id = session["user_id"]
    department = session.get("department", DEPARTMENTS[0])

    profile = connection.execute(
        "SELECT * FROM student_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    attendance = connection.execute(
        "SELECT * FROM attendance WHERE user_id = ? ORDER BY subject",
        (user_id,),
    ).fetchall()
    marks = connection.execute(
        "SELECT * FROM marks WHERE user_id = ? ORDER BY subject, id DESC",
        (user_id,),
    ).fetchall()
    assignments = connection.execute(
        """
        SELECT * FROM assignments
        WHERE department = ? OR department = ?
        ORDER BY due_date
        LIMIT 6
        """,
        (department, ALL_DEPARTMENTS),
    ).fetchall()
    opportunities = connection.execute(
        """
        SELECT * FROM opportunities
        WHERE department = ? OR department = ?
        ORDER BY deadline IS NULL, deadline
        LIMIT 8
        """,
        (department, ALL_DEPARTMENTS),
    ).fetchall()
    attempt = connection.execute(
        """
        SELECT * FROM quiz_attempts
        WHERE user_id = ?
        ORDER BY attempted_at DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    connection.close()

    attendance_metrics = []
    for row in attendance:
        percentage = round((row["attended"] / row["total_classes"]) * 100, 1) if row["total_classes"] else 0
        attendance_metrics.append({"subject": row["subject"], "percentage": percentage})

    marks_by_subject = {}
    for row in marks:
        marks_by_subject.setdefault(row["subject"], []).append(
            (row["score"] / row["max_score"] * 100) if row["max_score"] else 0
        )
    performance_metrics = [
        {"subject": subject, "percentage": round(sum(scores) / len(scores), 1)}
        for subject, scores in marks_by_subject.items()
    ]

    risk_alerts = []
    for item in attendance_metrics:
        if item["percentage"] < 75:
            risk_alerts.append({
                "level": "High risk",
                "title": f"Attendance needs attention in {item['subject']}",
                "detail": f"Your attendance is {item['percentage']}%. Aim for the next classes to recover.",
            })
    for item in performance_metrics:
        if item["percentage"] < 60:
            risk_alerts.append({
                "level": "Watch",
                "title": f"Strengthen your {item['subject']} performance",
                "detail": f"Your recorded average is {item['percentage']}%. Use the matching study materials before the next assessment.",
            })
    if not risk_alerts:
        risk_alerts.append({
            "level": "On track",
            "title": "Your academic signals look healthy",
            "detail": "Keep your attendance consistent and continue submitting work before the deadlines.",
        })

    skills = (profile["skills"] if profile and profile["skills"] else "").lower()
    career_interest = (profile["career_interest"] if profile and profile["career_interest"] else "").lower()
    career_terms = set(skills.replace(",", " ").split()) | set(career_interest.split())
    recommended_opportunities = []
    for opportunity in opportunities:
        searchable = f"{opportunity['title']} {opportunity['description'] or ''}".lower()
        match_count = sum(1 for term in career_terms if len(term) > 2 and term in searchable)
        recommended_opportunities.append((match_count, opportunity))
    recommended_opportunities.sort(key=lambda item: (-item[0], item[1]["deadline"] or "9999"))

    profile_fields = [
        profile["phone"], profile["enrollment_no"], profile["semester"],
        profile["cgpa"], profile["skills"], profile["career_interest"],
    ] if profile else []
    profile_completion = round(sum(bool(value) for value in profile_fields) / 6 * 100) if profile_fields else 0

    return render_template(
        "insights.html",
        attendance_metrics=attendance_metrics,
        performance_metrics=performance_metrics,
        risk_alerts=risk_alerts,
        assignments=assignments,
        recommended_opportunities=[item[1] for item in recommended_opportunities[:4]],
        profile_completion=profile_completion,
        latest_attempt=attempt,
    )


# ============================================================
# ONLINE QUIZ
# ============================================================

@app.route("/quiz", methods=["GET", "POST"])
@login_required
def quiz():

    connection = get_db_connection()

    quizzes = connection.execute(
        """
        SELECT *
        FROM quizzes
        WHERE department = ?
        ORDER BY id
        LIMIT 10
        """
        ,
        (session.get("department", DEPARTMENTS[0]),),
    ).fetchall()

    connection.close()

    result = None
    attempts = []

    if request.method == "POST":

        score = 0

        for question in quizzes:

            selected_answer = request.form.get(
                f"q{question['id']}"
            )

            if selected_answer == question["answer"]:
                score += 1

        total = len(quizzes)

        if total > 0:

            percentage = round(
                (score / total) * 100
            )

            connection = get_db_connection()
            connection.execute(
                """
                INSERT INTO quiz_attempts
                (user_id, department, score, total, percentage)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    session.get("department", DEPARTMENTS[0]),
                    score,
                    total,
                    percentage,
                ),
            )
            connection.commit()
            connection.close()

            result = (
                f"{score}/{total} "
                f"({percentage}%)"
            )

        else:

            result = "No quiz questions available."

    connection = get_db_connection()
    attempts = connection.execute(
        """
        SELECT * FROM quiz_attempts
        WHERE user_id = ?
        ORDER BY attempted_at DESC, id DESC
        LIMIT 10
        """,
        (session["user_id"],),
    ).fetchall()
    connection.close()

    return render_template(
        "quiz.html",
        quizzes=quizzes,
        result=result,
        attempts=attempts,
    )


# ============================================================
# COMPLAINT & FEEDBACK
# ============================================================

@app.route("/complaint", methods=["GET", "POST"])
@login_required
def complaint():

    if request.method == "POST":

        subject = request.form.get(
            "subject",
            "",
        ).strip()

        message = request.form.get(
            "message",
            "",
        ).strip()

        if not subject or not message:

            flash(
                "Subject and message are required.",
                "danger",
            )

            return render_template(
                "complaint.html"
            )

        connection = get_db_connection()

        connection.execute(
            """
            INSERT INTO complaints
            (user_id, subject, message)
            VALUES (?, ?, ?)
            """,
            (
                session["user_id"],
                subject,
                message,
            ),
        )

        connection.commit()
        connection.close()

        flash(
            "Complaint submitted successfully.",
            "success",
        )

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "complaint.html"
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin")
@login_required
def admin():

    if session.get("role") != "admin":
        return "Access denied", 403

    connection = get_db_connection()

    stats = {
        "students": connection.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE role = 'student'
            """
        ).fetchone()[0],

        "complaints": connection.execute(
            """
            SELECT COUNT(*)
            FROM complaints
            WHERE status != 'Resolved'
            """
        ).fetchone()[0],

        "notices": connection.execute(
            """
            SELECT COUNT(*)
            FROM notices
            """
        ).fetchone()[0],

        "events": connection.execute(
            """
            SELECT COUNT(*)
            FROM events
            """
        ).fetchone()[0],
    }

    complaints = connection.execute(
        """
        SELECT
            complaints.*,
            users.name
        FROM complaints
        JOIN users
            ON users.id = complaints.user_id
        ORDER BY complaints.id DESC
        """
    ).fetchall()

    active_attendance_sessions = connection.execute(
        """
        SELECT * FROM attendance_sessions
        WHERE active = 1
        ORDER BY id DESC
        LIMIT 20
        """
    ).fetchall()

    connection.close()

    return render_template(
        "admin.html",
        stats=stats,
        complaints=complaints,
        departments=DEPARTMENTS,
        active_attendance_sessions=active_attendance_sessions,
    )


# ============================================================
# UPDATE COMPLAINT STATUS
# ============================================================

@app.post("/admin/complaint/<int:id>")
@login_required
def update_complaint(id):

    if session.get("role") != "admin":
        return "Access denied", 403

    status = request.form.get(
        "status",
        "Pending",
    )

    allowed_statuses = {
        "Pending",
        "In Progress",
        "Resolved",
    }

    if status not in allowed_statuses:

        flash(
            "Invalid complaint status.",
            "danger",
        )

        return redirect(
            url_for("admin")
        )

    connection = get_db_connection()

    connection.execute(
        """
        UPDATE complaints
        SET status = ?
        WHERE id = ?
        """,
        (
            status,
            id,
        ),
    )

    connection.commit()
    connection.close()

    flash(
        "Complaint status updated successfully.",
        "success",
    )

    return redirect(
        url_for("admin")
    )


@app.post("/admin/content")
@login_required
def add_content():
    if session.get("role") != "admin":
        return "Access denied", 403

    content_type = request.form.get("content_type")
    connection = get_db_connection()

    try:
        if content_type == "notice":
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            if not title or not content:
                raise ValueError("Notice title and content are required.")
            connection.execute("INSERT INTO notices (title, content) VALUES (?, ?)", (title, content))
            message = "Notice published successfully."
        elif content_type == "event":
            title = request.form.get("title", "").strip()
            event_date = request.form.get("event_date", "").strip()
            description = request.form.get("description", "").strip()
            if not title or not event_date:
                raise ValueError("Event title and date are required.")
            connection.execute("INSERT INTO events (title, event_date, description) VALUES (?, ?, ?)", (title, event_date, description))
            message = "Event added successfully."
        elif content_type == "opportunity":
            title = request.form.get("title", "").strip()
            company = request.form.get("company", "").strip()
            opportunity_type = request.form.get("opportunity_type", "Job").strip()
            deadline = request.form.get("deadline", "").strip()
            link = request.form.get("link", "").strip() or "#"
            description = request.form.get("description", "").strip()
            if not title or not company:
                raise ValueError("Opportunity title and company are required.")
            connection.execute(
                """
                INSERT INTO opportunities
                (title, company, opportunity_type, deadline, link, description, department)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (title, company, opportunity_type, deadline, link, description, ALL_DEPARTMENTS),
            )
            message = "Career opportunity published successfully."
        elif content_type == "assignment":
            subject = request.form.get("subject", "").strip()
            title = request.form.get("title", "").strip()
            due_date = request.form.get("due_date", "").strip()
            description = request.form.get("description", "").strip()
            if not subject or not title or not due_date:
                raise ValueError("Assignment subject, title and due date are required.")
            connection.execute(
                "INSERT INTO assignments (department, subject, title, due_date, description) VALUES (?, ?, ?, ?, ?)",
                (ALL_DEPARTMENTS, subject, title, due_date, description),
            )
            message = "Assignment published successfully."
        else:
            raise ValueError("Select a valid content type.")

        connection.commit()
        flash(message, "success")
    except ValueError as error:
        flash(str(error), "danger")
    finally:
        connection.close()

    return redirect(url_for("admin"))


# ============================================================
# SMART CAMPUS CHAT ASSISTANT
# ============================================================

@app.route("/api/chat", methods=["POST"])
@login_required
def chat():

    data = request.get_json(
        silent=True
    ) or {}

    message = data.get(
        "message",
        "",
    ).strip().lower()

    if not message:

        return jsonify(
            {
                "reply": (
                    "Please enter a question."
                )
            }
        )

    connection = get_db_connection()
    user_id = session["user_id"]
    department = session.get("department", DEPARTMENTS[0])
    attendance_rows = connection.execute("SELECT attended, total_classes FROM attendance WHERE user_id = ?", (user_id,)).fetchall()
    attendance_subjects = connection.execute("SELECT subject, attended, total_classes FROM attendance WHERE user_id = ? ORDER BY subject", (user_id,)).fetchall()
    assignment_total = connection.execute("SELECT COUNT(*) FROM assignments WHERE department = ? OR department = ?", (department, ALL_DEPARTMENTS)).fetchone()[0]
    upcoming_assignments = connection.execute("SELECT subject, title, due_date FROM assignments WHERE department = ? OR department = ? ORDER BY due_date LIMIT 3", (department, ALL_DEPARTMENTS)).fetchall()
    opportunity_total = connection.execute("SELECT COUNT(*) FROM opportunities WHERE department = ? OR department = ?", (department, ALL_DEPARTMENTS)).fetchone()[0]
    timetable_total = connection.execute("SELECT COUNT(*) FROM timetable WHERE department = ? OR department = ?", (department, ALL_DEPARTMENTS)).fetchone()[0]
    next_classes = connection.execute("SELECT day, start_time, subject, room FROM timetable WHERE department = ? OR department = ? ORDER BY CASE day WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 ELSE 6 END, start_time LIMIT 2", (department, ALL_DEPARTMENTS)).fetchall()
    latest_notice = connection.execute("SELECT title, content FROM notices ORDER BY id DESC LIMIT 1").fetchone()
    latest_mark = connection.execute("SELECT subject, assessment, score, max_score FROM marks WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    unread_notifications = connection.execute("SELECT COUNT(*) FROM notifications WHERE (user_id IS NULL OR user_id = ?) AND is_read = 0", (user_id,)).fetchone()[0]
    connection.close()
    attendance_average = round(sum(row["attended"] / row["total_classes"] * 100 for row in attendance_rows if row["total_classes"]) / len([row for row in attendance_rows if row["total_classes"]]), 1) if attendance_rows else 0

    def reply(text):
        return jsonify({"reply": text})

    if any(word in message for word in ["attendance", "hazri", "hajri"]):
        details = "; ".join(f"{row['subject']}: {round(row['attended'] / row['total_classes'] * 100, 1) if row['total_classes'] else 0}%" for row in attendance_subjects)
        return reply(f"Your average attendance is {attendance_average}%. Subject-wise: {details or 'No attendance record yet.'}")
    if any(word in message for word in ["assignment", "deadline", "due", "submit"]):
        details = "; ".join(f"{row['title']} ({row['due_date']})" for row in upcoming_assignments)
        return reply(f"You have {assignment_total} assignments in your branch view. Upcoming: {details or 'No upcoming assignment found.'}")
    if any(word in message for word in ["timetable", "schedule", "next class", "meri class", "class kab"]):
        details = "; ".join(f"{row['day']} {row['start_time']} - {row['subject']} ({row['room'] or 'room pending'})" for row in next_classes)
        return reply(f"Your timetable has {timetable_total} classes. Next scheduled classes: {details or 'No classes found.'}")
    if any(word in message for word in ["placement", "career", "job", "internship", "naukri"]):
        return reply(f"There are {opportunity_total} career opportunities for your branch. Open Placement Desk to check eligibility and apply.")
    if any(word in message for word in ["mark", "marks", "result", "score", "cgpa"]):
        if latest_mark:
            return reply(f"Latest record: {latest_mark['subject']} - {latest_mark['assessment']}: {latest_mark['score']}/{latest_mark['max_score']}. Open Academic Hub for all marks.")
        return reply("No marks have been published yet. Your faculty can add them from the Faculty Portal.")
    if any(word in message for word in ["notice", "announcement", "khabar"]):
        return reply(f"Latest notice: {latest_notice['title']} - {latest_notice['content']}" if latest_notice else "There are no notices available right now.")
    if any(word in message for word in ["notification", "alert", "update"]):
        return reply(f"You have {unread_notifications} unread notification(s). Open Alerts to review them.")
    if any(word in message for word in ["material", "notes", "study", "padhai"]):
        return reply("Open Materials to access branch-specific notes, Wikipedia resources and YouTube tutorials.")
    if any(word in message for word in ["service", "library", "transport", "emergency"]):
        return reply("Open Campus Services for library, transport, emergency support, lost and found, lab booking and scholarships.")
    if any(word in message for word in ["password", "security", " ಸುರक्षा"]):
        return reply("Open Profile or Security Center to change your password and review account safeguards.")

    answers = {

        "notice": (
            "Please check the Notice Board "
            "on your dashboard."
        ),

        "exam": (
            "Exam schedules will be published "
            "through the Notice Board."
        ),

        "event": (
            "Upcoming events are shown "
            "in the Events section."
        ),

        "notes": (
            "Open Digital Learning to access "
            "study materials."
        ),

        "attendance": (
            "Attendance analytics can be "
            "connected to the college "
            "attendance database."
        ),

        "job": (
            "Open the Jobs & Internships section "
            "on your dashboard for the latest career updates."
        ),

        "internship": (
            "Open the Jobs & Internships section "
            "on your dashboard for current opportunities."
        ),

        "profile": (
            "Open Profile to save your academic record, "
            "skills and career interests."
        ),

        "hello": (
            "Hello! I am your Smart Campus "
            "Assistant. How can I help?"
        ),

        "hi": (
            "Hello! I am your Smart Campus "
            "Assistant. How can I help?"
        ),
    }

    for keyword, response in answers.items():

        if keyword in message:

            return jsonify(
                {
                    "reply": response
                }
            )

    return jsonify(
        {
            "reply": (
                "I can help with notices, exams, "
                "events, notes and attendance. "
                "Please ask a campus-related question."
            )
        }
    )


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":
    try:
        init_db()
    except RuntimeError as exc:
        print(f"Firebase startup failed: {exc}")
        print(
            "Open Firebase Console -> Firestore Database -> Create database, "
            "then run this command again."
        )
        raise SystemExit(1) from exc

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
    )