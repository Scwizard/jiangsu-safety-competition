import sqlite3
import json
import os
import re
import sys
import shutil
import difflib
import unicodedata

DB_FILE = "database.db"
LEGACY_FILE = "database_old.db"          # 修复：原来误写成 database.db，兜底查询等于把同一张表再查一遍
_SCHEMA_READY = False

# 零宽字符：题干里混进 U+200C/U+200B 这类东西肉眼看不出，但会让字符串相等判断直接失败
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u200e\u200f\ufeff\u00a0"))

def connect():
    return sqlite3.connect(DB_FILE)

def seedFromBundle():
    # 只有把 database.db 打进 exe（--add-data "database.db;."）时才生效：内嵌的那份会被解到临时目录，
    # 首次运行把它落到程序目录，保证题库可读、可写、可留存。题库放在程序旁边时这里什么都不做。
    if os.path.exists(DB_FILE):
        return
    bundled = os.path.join(getattr(sys, "_MEIPASS", ""), DB_FILE)
    if getattr(sys, "frozen", False) and os.path.exists(bundled):
        try:
            shutil.copyfile(bundled, DB_FILE)
        except OSError:
            pass

def ensureSchema():
    # question 上有唯一索引，写库才能幂等
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    seedFromBundle()
    conn = connect()
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS tiku ("question" TEXT, "answer" TEXT)')
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tiku_question ON tiku(question)")
        conn.execute('CREATE TABLE IF NOT EXISTS tiku_detail ("question" TEXT PRIMARY KEY, "title" TEXT, "options" TEXT)')
        # 题干归一化后的指纹，换届后靠它把旧题答案搬到新 questionId 上
        conn.execute('CREATE TABLE IF NOT EXISTS tiku_title ("fingerprint" TEXT, "question" TEXT)')
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tiku_title_fp ON tiku_title(fingerprint)")
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
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % LEGACY_FILE, uri=True)
    except sqlite3.Error:
        return 0
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
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % LEGACY_FILE, uri=True)
    except sqlite3.Error:
        return rows
    try:
        return conn.execute("SELECT question, answer FROM tiku WHERE question = ?", (question,)).fetchall()
    except sqlite3.Error:
        return rows
    finally:
        conn.close()

def insertDetail(question, title, optionList):
    # 归档题干与选项，换届后可以按题干文本重新映射答案
    ensureSchema()
    conn = connect()
    try:
        conn.execute("INSERT OR REPLACE INTO tiku_detail (question, title, options) VALUES (?, ?, ?)",
                     (question, title, json.dumps(optionList, ensure_ascii=False)))
        conn.execute("DELETE FROM tiku_title WHERE question = ?", (question,))
        fingerprint = normalizeText(title)
        if fingerprint:
            conn.execute("INSERT INTO tiku_title (fingerprint, question) VALUES (?, ?)", (fingerprint, question))
        conn.commit()
        _TITLE_CACHE.clear()
        return True
    except sqlite3.Error:
        conn.rollback()
        return None
    finally:
        conn.close()


# ============================ 换届迁移：按题干把旧答案搬到新题上 ============================

_TITLE_CACHE = {}

def normalizeText(text):
    """题干/选项指纹：去零宽字符、全角转半角、去所有空白、转小写。

    平台同一道题的题干标点全半角会变（"取用化学试剂时,应遵循" / "取用化学试剂时，应遵循"），
    直接字符串相等会漏掉，必须归一化后再比。
    """
    if text is None:
        return ""
    text = str(text).translate(_ZERO_WIDTH)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", "", text)
    return text.lower()

def _rebuildTitleIndex():
    """fingerprint -> [(旧questionId, 旧选项列表)]，进程内建一次就够（题库万级也就几十毫秒）。"""
    if _TITLE_CACHE:
        return _TITLE_CACHE
    ensureSchema()
    rows = []
    conn = connect()
    try:
        rows = conn.execute("SELECT question, title, options FROM tiku_detail").fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        conn.close()
    for question, title, optionsRaw in rows:
        fingerprint = normalizeText(title)
        if not fingerprint:
            continue
        try:
            options = json.loads(optionsRaw)
        except (TypeError, ValueError):
            options = []
        _TITLE_CACHE.setdefault(fingerprint, []).append((question, options))
    return _TITLE_CACHE

def _legacyCorrectContents(options):
    """从归档选项里取正确答案的内容指纹。优先 isCorrect，没有就用 tiku 里的 answer id 反查。"""
    contents = set()
    for option in options:
        if option.get("isCorrect") == 1:
            contents.add(normalizeText(option.get("content")))
    return contents

def lookupAnswer(questionId, title, optionList):
    """返回 (answerIds, how)。

    answerIds 为逗号分隔的新选项 id，匹配不到返回 None。
    顺序：questionId 直命 -> 题干指纹精确命中 -> 题干模糊命中 -> 按选项内容把旧答案翻译成新选项 id。
    """
    rows = request_data(questionId)
    if rows and rows[0][1]:
        return rows[0][1], "id"

    fingerprint = normalizeText(title)
    if not fingerprint:
        return None, "no-title"

    candidates = _rebuildTitleIndex().get(fingerprint)
    how = "title"
    if not candidates:
        candidates = _fuzzyCandidates(fingerprint)
        how = "title-fuzzy"
    if not candidates:
        return None, "title-unknown"

    # 新卷的选项：内容指纹 -> 新 id
    newByContent = {}
    for option in optionList:
        newByContent.setdefault(normalizeText(option.get("content")), option["id"])

    for oldQuestionId, oldOptions in candidates:
        rightContents = _legacyCorrectContents(oldOptions)
        if not rightContents:
            # 归档里没有 isCorrect 标记时，用旧库 answer 的选项 id 去反查内容
            oldAnswer = request_data(oldQuestionId)
            if not oldAnswer or not oldAnswer[0][1]:
                continue
            oldIds = set(oldAnswer[0][1].split(","))
            rightContents = {normalizeText(o.get("content")) for o in oldOptions if o.get("id") in oldIds}
        if not rightContents:
            continue
        picked = [o["id"] for o in optionList if normalizeText(o.get("content")) in rightContents]
        if not picked:
            continue
        covered = sum(1 for o in optionList if normalizeText(o.get("content")) in rightContents)
        return ",".join(picked), how if covered == len(rightContents) else how + "-partial"

    return None, "option-mismatch"


def _fuzzyCandidates(fingerprint, threshold=0.90):
    """题干被改过一两个字时的兜底：长度接近 + 字符重合度高 + 序列相似度过阈值。"""
    index = _rebuildTitleIndex()
    if not index:
        return []
    target = set(fingerprint)
    limit = max(6, len(fingerprint) // 5)
    scored = []
    for candidate, payload in index.items():
        if abs(len(candidate) - len(fingerprint)) > limit:
            continue
        if len(target & set(candidate)) < len(target) * 0.8:
            continue
        ratio = difflib.SequenceMatcher(None, fingerprint, candidate).ratio()
        if ratio >= threshold:
            scored.append((ratio, payload))
    if not scored:
        return []
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1]

def migrateQuestion(questionId, title, answerIds, optionList):
    """把这次映射到的答案按新 questionId 落库，下次考试就能 ID 直命，越跑越快。"""
    state = insert_data(questionId, answerIds)
    insertDetail(questionId, title, optionList)
    return state

def backfillTitleIndex():
    """把历史 tiku_detail 的题干指纹补进 tiku_title。启动时跑一次，重复执行无副作用。"""
    ensureSchema()
    conn = connect()
    try:
        have = {row[0] for row in conn.execute("SELECT question FROM tiku_title")}
        rows = conn.execute("SELECT question, title FROM tiku_detail").fetchall()
        pending = []
        for question, title in rows:
            if question in have:
                continue
            fingerprint = normalizeText(title)
            if fingerprint:
                pending.append((fingerprint, question))
        if pending:
            conn.executemany("INSERT INTO tiku_title (fingerprint, question) VALUES (?, ?)", pending)
            conn.commit()
        return len(pending)
    except sqlite3.Error:
        return 0
    finally:
        conn.close()
