import sqlite3
import json
import os

DB_FILE = "database.db"
LEGACY_FILE = "database.db"
_SCHEMA_READY = False

def connect():
    return sqlite3.connect(DB_FILE)

def ensureSchema():
    # question 上有唯一索引，写库才能幂等
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    conn = connect()
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS tiku ("question" TEXT, "answer" TEXT)')
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tiku_question ON tiku(question)")
        conn.execute('CREATE TABLE IF NOT EXISTS tiku_detail ("question" TEXT PRIMARY KEY, "title" TEXT, "options" TEXT)')
        conn.commit()
        _SCHEMA_READY = True
    finally:
        conn.close()

def count_questions():
    ensureSchema()
    conn = connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM tiku").fetchone()[0]
    finally:
        conn.close()

def count_details():
    ensureSchema()
    conn = connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM tiku_detail").fetchone()[0]
    finally:
        conn.close()

def count_legacy():
    if not os.path.exists(LEGACY_FILE):
        return 0
    conn = sqlite3.connect("file:%s?mode=ro" % LEGACY_FILE, uri=True)
    try:
        return conn.execute("SELECT COUNT(*) FROM tiku").fetchone()[0]
    except sqlite3.Error:
        return 0
    finally:
        conn.close()

def insert_data(question, answer):
    # 新增或更新返回 True，已有且一致返回 False，出错返回 None
    ensureSchema()
    conn = connect()
    try:
        row = conn.execute("SELECT answer FROM tiku WHERE question = ?", (question,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO tiku (question, answer) VALUES (?, ?)", (question, answer))
            conn.commit()
            return True
        if row[0] != answer:
            conn.execute("UPDATE tiku SET answer = ? WHERE question = ?", (answer, question))
            conn.commit()
            return True
        return False
    except sqlite3.Error:
        conn.rollback()
        return None
    finally:
        conn.close()

def request_data(question):
    ensureSchema()
    conn = connect()
    try:
        rows = conn.execute("SELECT question, answer FROM tiku WHERE question = ?", (question,)).fetchall()
    finally:
        conn.close()
    if rows or not os.path.exists(LEGACY_FILE):
        return rows
    conn = sqlite3.connect("file:%s?mode=ro" % LEGACY_FILE, uri=True)
    try:
        return conn.execute("SELECT question, answer FROM tiku WHERE question = ?", (question,)).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()

def insertDetail(question, title, optionList):
    # 归档题干与选项，换届后可以按题干文本重新映射答案
    ensureSchema()
    conn = connect()
    try:
        conn.execute("INSERT OR REPLACE INTO tiku_detail (question, title, options) VALUES (?, ?, ?)",
                     (question, title, json.dumps(optionList, ensure_ascii=False)))
        conn.commit()
        return True
    except sqlite3.Error:
        conn.rollback()
        return None
    finally:
        conn.close()
