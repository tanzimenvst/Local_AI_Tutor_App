import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "tutor.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tutors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            tutor_type TEXT NOT NULL,
            system_prompt TEXT NOT NULL,
            model TEXT NOT NULL DEFAULT 'qwen3:8b',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tutor_id INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            audio_url TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (tutor_id) REFERENCES tutors(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tutor_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tutor_id INTEGER NOT NULL,
            assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(user_id, tutor_id),

            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (tutor_id) REFERENCES tutors(id)
        )
    """)
    # Ensure there is a general AI room available to everyone
    cursor.execute("SELECT id FROM tutors WHERE tutor_type = 'general'")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO tutors (name, tutor_type, system_prompt, model)
            VALUES (?, ?, ?, ?)
        """, ("Local AI Assistant", "general", "You are a helpful and extremely intelligent general-purpose AI assistant. Answer the user's questions clearly and accurately. Be polite and concise.", "qwen2.5:1.5b"))

    connection.commit()
    connection.close()

def get_user_by_username(username: str):
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    connection.close()
    return user


def get_user_by_id(user_id: int):
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    connection.close()
    return user


def get_tutor_by_id(tutor_id: int):
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM tutors WHERE id = ?", (tutor_id,))
    tutor = cursor.fetchone()
    connection.close()
    return tutor


def get_assigned_tutors(user_id: int):
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("""
        SELECT DISTINCT t.* 
        FROM tutors t
        LEFT JOIN tutor_assignments ta ON t.id = ta.tutor_id
        WHERE ta.user_id = ? OR t.tutor_type = 'general'
    """, (user_id,))
    tutors = cursor.fetchall()
    connection.close()
    return tutors


def get_all_users():
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    connection.close()
    return users


def get_all_tutors():
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM tutors")
    tutors = cursor.fetchall()
    connection.close()
    return tutors


def create_user(username, display_name, password_hash, is_admin=0):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (username, display_name, password_hash, is_admin)
            VALUES (?, ?, ?, ?)
        """, (username, display_name, password_hash, is_admin))
        connection.commit()
    finally:
        connection.close()


def create_tutor(name, tutor_type, system_prompt, model="qwen3:8b"):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO tutors (name, tutor_type, system_prompt, model)
            VALUES (?, ?, ?, ?)
        """, (name, tutor_type, system_prompt, model))
        connection.commit()
    finally:
        connection.close()


def assign_tutor(user_id, tutor_id):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO tutor_assignments (user_id, tutor_id)
            VALUES (?, ?)
        """, (user_id, tutor_id))
        connection.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        connection.close()


def add_message(user_id, tutor_id, prompt, response, audio_url=None):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO messages (user_id, tutor_id, prompt, response, audio_url)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, tutor_id, prompt, response, audio_url))
        connection.commit()
    finally:
        connection.close()


def get_messages(user_id, tutor_id, limit=20):
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("""
        SELECT * FROM (
            SELECT * FROM messages 
            WHERE user_id = ? AND tutor_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ) ORDER BY created_at ASC
    """, (user_id, tutor_id, limit))
    messages = cursor.fetchall()
    connection.close()
    return messages


def clear_messages(user_id, tutor_id):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            DELETE FROM messages 
            WHERE user_id = ? AND tutor_id = ?
        """, (user_id, tutor_id))
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized: {DB_PATH}")