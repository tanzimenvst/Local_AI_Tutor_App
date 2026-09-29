import sqlite3
from database import get_connection

def seed_database():
    connection = get_connection()
    cursor = connection.cursor()
    
    # 1. Create Tutors
    tech_prompt = "You are a technical tutor. Ask basic tech questions, correct mistakes, and correct English."
    eng_prompt = "You are an English tutor for a non-technical user. Focus on conversation and correcting grammar gracefully."
    
    try:
        cursor.execute("""
            INSERT INTO tutors (name, tutor_type, system_prompt, model)
            VALUES ('Technical Tutor', 'technical', ?, 'qwen3:8b')
        """, (tech_prompt,))
        tech_tutor_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO tutors (name, tutor_type, system_prompt, model)
            VALUES ('English Tutor', 'english', ?, 'qwen3:8b')
        """, (eng_prompt,))
        eng_tutor_id = cursor.lastrowid
        print("Tutors created successfully.")
    except Exception as e:
        print(f"Error creating tutors (they might already exist): {e}")
        cursor.execute("SELECT id FROM tutors WHERE tutor_type = 'technical'")
        tech_tutor_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM tutors WHERE tutor_type = 'english'")
        eng_tutor_id = cursor.fetchone()[0]

    # 2. Get Admin User
    cursor.execute("SELECT id FROM users WHERE is_admin = 1 LIMIT 1")
    admin_row = cursor.fetchone()
    
    if not admin_row:
        print("No admin user found! Please run create_admin.py first.")
        connection.close()
        return
        
    admin_id = admin_row[0]
    
    # 3. Assign both tutors to Admin
    try:
        cursor.execute("""
            INSERT INTO tutor_assignments (user_id, tutor_id)
            VALUES (?, ?)
        """, (admin_id, tech_tutor_id))
        
        cursor.execute("""
            INSERT INTO tutor_assignments (user_id, tutor_id)
            VALUES (?, ?)
        """, (admin_id, eng_tutor_id))
        
        connection.commit()
        print("Assigned both tutors to the admin user.")
    except sqlite3.IntegrityError:
        print("Tutors are already assigned to this user.")
        
    connection.close()

if __name__ == "__main__":
    seed_database()
