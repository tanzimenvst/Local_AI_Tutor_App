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
            is_blocked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tutors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            is_general INTEGER NOT NULL DEFAULT 0,
            system_prompt TEXT NOT NULL,
            model TEXT NOT NULL DEFAULT 'qwen3:8b',
            configuration TEXT,
            is_blocked INTEGER NOT NULL DEFAULT 0,
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tutor_id INTEGER NOT NULL,
            message_count INTEGER NOT NULL DEFAULT 0,
            evaluation_data TEXT, 
            
            UNIQUE(user_id, tutor_id),
            
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (tutor_id) REFERENCES tutors(id)
        )
    """)
    # Ensure there is a general AI room available to everyone
    cursor.execute("SELECT id FROM tutors WHERE is_general = 1")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO tutors (name, is_general, system_prompt, model)
            VALUES (?, 1, ?, ?)
        """, ("Local AI Assistant", "You are a helpful and extremely intelligent general-purpose AI assistant. Answer the user's questions clearly and accurately. Be polite and concise.", "qwen3:8b"))

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
        WHERE ta.user_id = ? OR t.is_general = 1
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


def update_user_details(user_id, username, display_name, password_hash=None):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if password_hash:
            cursor.execute("UPDATE users SET username = ?, display_name = ?, password_hash = ? WHERE id = ?", (username, display_name, password_hash, user_id))
        else:
            cursor.execute("UPDATE users SET username = ?, display_name = ? WHERE id = ?", (username, display_name, user_id))
        connection.commit()
    except sqlite3.IntegrityError:
        return False
    finally:
        connection.close()
    return True


def create_tutor(name, system_prompt, model="qwen3:8b", configuration=None):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO tutors (name, system_prompt, model, configuration)
            VALUES (?, ?, ?, ?)
        """, (name, system_prompt, model, configuration))
        connection.commit()
        return True
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


def update_user_role(user_id, is_admin):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin, user_id))
        connection.commit()
    finally:
        connection.close()


def update_user_assignments(user_id, tutor_ids):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        # Delete old explicit assignments
        cursor.execute("DELETE FROM tutor_assignments WHERE user_id = ?", (user_id,))
        # Insert new ones
        for t_id in tutor_ids:
            cursor.execute("INSERT INTO tutor_assignments (user_id, tutor_id) VALUES (?, ?)", (user_id, t_id))
        connection.commit()
    finally:
        connection.close()


def toggle_block_user(user_id):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        # Toggle is_blocked between 1 and 0
        cursor.execute("UPDATE users SET is_blocked = 1 - is_blocked WHERE id = ?", (user_id,))
        connection.commit()
    finally:
        connection.close()


def delete_user(user_id):
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    try:
        # First, delete all audio files for this user's messages
        cursor.execute("SELECT audio_url FROM messages WHERE user_id = ? AND audio_url IS NOT NULL", (user_id,))
        rows = cursor.fetchall()
        for row in rows:
            if row['audio_url']:
                filename = row['audio_url'].split('/')[-1]
                file_path = BASE_DIR / "static" / "audio" / filename
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except OSError:
                        pass
                        
        # Delete records
        cursor.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM tutor_assignments WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        connection.commit()
    finally:
        connection.close()




def add_message(user_id, tutor_id, prompt, response, audio_url=None):
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO messages (user_id, tutor_id, prompt, response, audio_url)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, tutor_id, prompt, response, audio_url))
        
        # Enforce max 20 messages limit
        cursor.execute("""
            SELECT id, audio_url FROM messages
            WHERE user_id = ? AND tutor_id = ?
            ORDER BY created_at DESC
            LIMIT -1 OFFSET 20
        """, (user_id, tutor_id))
        
        old_messages = cursor.fetchall()
        for msg in old_messages:
            if msg['audio_url']:
                filename = msg['audio_url'].split('/')[-1]
                file_path = BASE_DIR / "static" / "audio" / filename
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except OSError:
                        pass
            
            cursor.execute("DELETE FROM messages WHERE id = ?", (msg['id'],))

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
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT audio_url FROM messages WHERE user_id = ? AND tutor_id = ? AND audio_url IS NOT NULL", (user_id, tutor_id))
        rows = cursor.fetchall()
        for row in rows:
            if row['audio_url']:
                filename = row['audio_url'].split('/')[-1]
                file_path = BASE_DIR / "static" / "audio" / filename
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except OSError:
                        pass

        cursor.execute("""
            DELETE FROM messages 
            WHERE user_id = ? AND tutor_id = ?
        """, (user_id, tutor_id))
        connection.commit()
    finally:
        connection.close()


def update_tutor_details(tutor_id, name, system_prompt, configuration=None):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if configuration is not None:
            cursor.execute("UPDATE tutors SET name = ?, system_prompt = ?, configuration = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (name, system_prompt, configuration, tutor_id))
        else:
            cursor.execute("UPDATE tutors SET name = ?, system_prompt = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (name, system_prompt, tutor_id))
        connection.commit()
    finally:
        connection.close()
    return True


def update_tutor_model(tutor_id, model):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE tutors SET model = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (model, tutor_id))
        connection.commit()
    finally:
        connection.close()


def toggle_block_tutor(tutor_id):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE tutors SET is_blocked = 1 - is_blocked, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (tutor_id,))
        connection.commit()
    finally:
        connection.close()


def delete_tutor(tutor_id):
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    try:
        # First, delete all audio files for this tutor's messages
        cursor.execute("SELECT audio_url FROM messages WHERE tutor_id = ? AND audio_url IS NOT NULL", (tutor_id,))
        rows = cursor.fetchall()
        for row in rows:
            if row['audio_url']:
                filename = row['audio_url'].split('/')[-1]
                file_path = BASE_DIR / "static" / "audio" / filename
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except OSError:
                        pass
                        
        # Delete records
        cursor.execute("DELETE FROM messages WHERE tutor_id = ?", (tutor_id,))
        cursor.execute("DELETE FROM tutor_assignments WHERE tutor_id = ?", (tutor_id,))
        cursor.execute("DELETE FROM tutors WHERE id = ?", (tutor_id,))
        connection.commit()
    finally:
        connection.close()


def get_user_evaluation(user_id: int, tutor_id: int):
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM user_evaluations WHERE user_id = ? AND tutor_id = ?", (user_id, tutor_id))
    row = cursor.fetchone()
    connection.close()
    
    if not row:
        return {"message_count": 0, "evaluation_data": None}
    
    import json
    eval_data = {}
    if row["evaluation_data"]:
        try:
            eval_data = json.loads(row["evaluation_data"])
        except:
            pass
            
    return {
        "message_count": row["message_count"],
        "evaluation_data": eval_data
    }

def increment_evaluation_message_count(user_id: int, tutor_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        INSERT INTO user_evaluations (user_id, tutor_id, message_count) 
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, tutor_id) DO UPDATE SET message_count = message_count + 1
    """, (user_id, tutor_id))
    connection.commit()
    connection.close()
    
def update_user_evaluation_data(user_id: int, tutor_id: int, eval_data: dict):
    import json
    data_str = json.dumps(eval_data)
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        INSERT INTO user_evaluations (user_id, tutor_id, evaluation_data) 
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, tutor_id) DO UPDATE SET evaluation_data = ?
    """, (user_id, tutor_id, data_str, data_str))
    connection.commit()
    connection.close()

if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized: {DB_PATH}")