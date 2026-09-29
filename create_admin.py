import sqlite3
from werkzeug.security import generate_password_hash
from database import get_connection

def create_admin(username, password, display_name):
    connection = get_connection()
    cursor = connection.cursor()
    
    password_hash = generate_password_hash(password)
    
    try:
        cursor.execute("""
            INSERT INTO users (username, display_name, password_hash, is_admin)
            VALUES (?, ?, ?, 1)
        """, (username, display_name, password_hash))
        connection.commit()
        print(f"Admin user '{username}' created successfully.")
    except sqlite3.IntegrityError:
        print(f"Error: User '{username}' already exists.")
    finally:
        connection.close()

if __name__ == "__main__":
    print("--- Create Admin User ---")
    username = input("Enter admin username: ").strip()
    display_name = input("Enter admin display name: ").strip()
    password = input("Enter admin password: ").strip()
    
    if username and display_name and password:
        create_admin(username, password, display_name)
    else:
        print("All fields are required.")
