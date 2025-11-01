import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

def insert_data(question, answer):
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tiku (question, answer)
            VALUES (?, ?)
        """, (question, answer))

        conn.commit()
        return True
        
    except sqlite3.Error:
        if conn:
            conn.rollback()
            return False
            
    except Exception:
        return False
        
    finally:
        # 关闭连接
        if conn:
            conn.close()

def request_data(question):
    # 从数据库获取答案然后组装元组
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    cursor.execute(f'''
    SELECT question, answer 
    FROM tiku 
    WHERE question is "%s"
    ORDER BY question
    '''% question)
    
    records = cursor.fetchall()
    conn.close()
    return records