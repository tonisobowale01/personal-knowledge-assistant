import sqlite3

from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "chat_history.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            course TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats(id)
        )
    """)

    conn.commit()
    conn.close()

def create_chat(title, course=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO chats (title, course) VALUES (?, ?)
        """, (title, course)
    )

    chat_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return chat_id

def add_message(chat_id, role, content):
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO message (chat_id, role, content) VALUES (?, ?, ?)",
                (chat_id, role, content),
            )
    finally:
        conn.close()


def get_messages(chat_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role, content, created_at FROM message WHERE chat_id = ? ORDER BY id
        """, (chat_id,)
    )

    rows = cursor.fetchall()

    conn.close()

    return rows

def get_chats():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, course, created_at FROM chats ORDER BY id DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows

if __name__ == "__main__":
    initialize_database()

    chat_id = create_chat(
        "OS Scheduling Review",
        "Operating Systems"
    )

    chats = get_chats()

    for chat in chats:
        print(chat)

    # add_message(chat_id, "user", "Explain SJF")
    # add_message(chat_id, "assistant", "SJF chooses the shortest job first.")

    messages = get_messages(chat_id)

    print(messages)

    print("Created chat:", chat_id)


def get_chat(chat_id):
    conn = get_connection()
    try:
        return conn.execute("SELECT id, title, course FROM chats WHERE id = ?", (chat_id,)).fetchone()
    finally:
        conn.close()


def add_exchange(chat_id, question, answer):
    conn = get_connection()
    try:
        with conn:
            conn.executemany(
                "INSERT INTO message (chat_id, role, content) VALUES (?, ?, ?)",
                [(chat_id, "user", question), (chat_id, "assistant", answer)],
            )
    finally:
        conn.close()


def rename_chat(chat_id, title):
    conn = get_connection()
    try:
        with conn:
            return conn.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id)).rowcount > 0
    finally:
        conn.close()


def delete_chat(chat_id):
    conn = get_connection()
    try:
        with conn:
            if conn.execute("SELECT id FROM chats WHERE id = ?", (chat_id,)).fetchone() is None:
                return False
            conn.execute("DELETE FROM message WHERE chat_id = ?", (chat_id,))
            conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            return True
    finally:
        conn.close()
