
from __future__ import annotations
import sqlite3
from pathlib import Path
from PySide6.QtCore import QStandardPaths

def bundled_db_path():
    return Path(__file__).resolve().parent.parent / "data" / "bible.db"

def user_db_path():
    base = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    base.mkdir(parents=True, exist_ok=True)
    return base / "annotations.db"

def scripture_conn():
    c = sqlite3.connect(bundled_db_path())
    c.row_factory = sqlite3.Row
    return c

def annotations_conn():
    c = sqlite3.connect(user_db_path())
    c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS notes_v2(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      book_number INTEGER NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL,
      translation_code TEXT, note_text TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(book_number,chapter,verse,translation_code)
    );
    CREATE TABLE IF NOT EXISTS highlights_v2(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      book_number INTEGER NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL,
      translation_code TEXT, color TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(book_number,chapter,verse,translation_code)
    );
    CREATE TABLE IF NOT EXISTS bookmarks_v2(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      book_number INTEGER NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL,
      translation_code TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(book_number,chapter,verse,translation_code)
    );
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    """)
    c.commit()
    return c

def get_translations():
    with scripture_conn() as c:
        return c.execute("SELECT * FROM translations ORDER BY id").fetchall()

def get_translation(code):
    with scripture_conn() as c:
        return c.execute("SELECT * FROM translations WHERE code=?", (code,)).fetchone()

def get_books(code):
    with scripture_conn() as c:
        return c.execute("""
        SELECT DISTINCT b.book_number,b.testament,b.name
        FROM canonical_books b JOIN verses v ON v.book_number=b.book_number
        JOIN translations t ON t.id=v.translation_id
        WHERE t.code=? ORDER BY b.book_number
        """, (code,)).fetchall()

def get_chapters(code,book_number):
    with scripture_conn() as c:
        return [int(r["chapter"]) for r in c.execute("""
        SELECT DISTINCT v.chapter FROM verses v
        JOIN translations t ON t.id=v.translation_id
        WHERE t.code=? AND v.book_number=? ORDER BY v.chapter
        """, (code,book_number)).fetchall()]

def get_chapter(code,book_number,chapter):
    with scripture_conn() as c:
        return c.execute("""
        SELECT v.id,v.book_number,v.chapter,v.verse,v.text_raw,v.text_clean,
               b.name AS book,t.code AS translation_code,t.name AS translation_name,t.edition_type
        FROM verses v JOIN canonical_books b ON b.book_number=v.book_number
        JOIN translations t ON t.id=v.translation_id
        WHERE t.code=? AND v.book_number=? AND v.chapter=? ORDER BY v.verse
        """, (code,book_number,chapter)).fetchall()

def search_verses(code,query,limit=200):
    query = query.strip()
    if not query: return []
    with scripture_conn() as c:
        tr = c.execute("SELECT id FROM translations WHERE code=?", (code,)).fetchone()
        if not tr: return []
        tid = int(tr["id"])
        try:
            return c.execute("""
            SELECT v.id,v.book_number,b.name AS book,v.chapter,v.verse,v.text_clean,v.text_raw
            FROM verse_fts f JOIN verses v ON v.id=f.rowid
            JOIN canonical_books b ON b.book_number=v.book_number
            WHERE verse_fts MATCH ? AND v.translation_id=?
            ORDER BY rank LIMIT ?
            """, (query,tid,limit)).fetchall()
        except sqlite3.OperationalError:
            return c.execute("""
            SELECT v.id,v.book_number,b.name AS book,v.chapter,v.verse,v.text_clean,v.text_raw
            FROM verses v JOIN canonical_books b ON b.book_number=v.book_number
            WHERE v.translation_id=? AND v.text_clean LIKE ?
            ORDER BY v.book_number,v.chapter,v.verse LIMIT ?
            """, (tid,f"%{query}%",limit)).fetchall()

def get_annotations_for_rows(rows,code):
    notes,highlights,bookmarks = {},{},set()
    with annotations_conn() as c:
        for r in rows:
            key=(int(r["book_number"]),int(r["chapter"]),int(r["verse"]))
            b,ch,v=key
            n=c.execute("""SELECT note_text FROM notes_v2 WHERE book_number=? AND chapter=? AND verse=?
                AND (translation_code IS NULL OR translation_code=?)
                ORDER BY CASE WHEN translation_code=? THEN 0 ELSE 1 END LIMIT 1""",(b,ch,v,code,code)).fetchone()
            if n: notes[key]=n["note_text"]
            h=c.execute("""SELECT color FROM highlights_v2 WHERE book_number=? AND chapter=? AND verse=?
                AND (translation_code IS NULL OR translation_code=?)
                ORDER BY CASE WHEN translation_code=? THEN 0 ELSE 1 END LIMIT 1""",(b,ch,v,code,code)).fetchone()
            if h: highlights[key]=h["color"]
            bm=c.execute("""SELECT 1 FROM bookmarks_v2 WHERE book_number=? AND chapter=? AND verse=?
                AND (translation_code IS NULL OR translation_code=?) LIMIT 1""",(b,ch,v,code)).fetchone()
            if bm: bookmarks.add(key)
    return notes,highlights,bookmarks

def get_note(b,ch,v,code=None):
    with annotations_conn() as c:
        r=c.execute("SELECT note_text FROM notes_v2 WHERE book_number=? AND chapter=? AND verse=? AND translation_code IS ?",
                    (b,ch,v,code)).fetchone()
        return r["note_text"] if r else ""

def save_note(b,ch,v,text,code=None):
    with annotations_conn() as c:
        if text.strip():
            c.execute("""INSERT INTO notes_v2(book_number,chapter,verse,translation_code,note_text)
            VALUES(?,?,?,?,?)
            ON CONFLICT(book_number,chapter,verse,translation_code)
            DO UPDATE SET note_text=excluded.note_text,updated_at=CURRENT_TIMESTAMP""",(b,ch,v,code,text.strip()))
        else:
            c.execute("DELETE FROM notes_v2 WHERE book_number=? AND chapter=? AND verse=? AND translation_code IS ?",
                      (b,ch,v,code))
        c.commit()

def set_highlight(b,ch,v,color,code=None):
    with annotations_conn() as c:
        if color:
            c.execute("""INSERT INTO highlights_v2(book_number,chapter,verse,translation_code,color)
            VALUES(?,?,?,?,?)
            ON CONFLICT(book_number,chapter,verse,translation_code)
            DO UPDATE SET color=excluded.color""",(b,ch,v,code,color))
        else:
            c.execute("DELETE FROM highlights_v2 WHERE book_number=? AND chapter=? AND verse=? AND translation_code IS ?",
                      (b,ch,v,code))
        c.commit()

def toggle_bookmark(b,ch,v,code=None):
    with annotations_conn() as c:
        exists=c.execute("SELECT 1 FROM bookmarks_v2 WHERE book_number=? AND chapter=? AND verse=? AND translation_code IS ?",
                         (b,ch,v,code)).fetchone()
        if exists:
            c.execute("DELETE FROM bookmarks_v2 WHERE book_number=? AND chapter=? AND verse=? AND translation_code IS ?",
                      (b,ch,v,code)); result=False
        else:
            c.execute("INSERT INTO bookmarks_v2(book_number,chapter,verse,translation_code) VALUES(?,?,?,?)",
                      (b,ch,v,code)); result=True
        c.commit()
        return result

def get_setting(key,default=None):
    with annotations_conn() as c:
        r=c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

def set_setting(key,value):
    with annotations_conn() as c:
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(key,str(value)))
        c.commit()


def get_parallel_chapter(primary_code, secondary_code, book_number, chapter):
    primary = get_chapter(primary_code, book_number, chapter)
    secondary = get_chapter(secondary_code, book_number, chapter)
    pmap = {int(r["verse"]): r for r in primary}
    smap = {int(r["verse"]): r for r in secondary}
    verse_numbers = sorted(set(pmap) | set(smap))
    return [(v, pmap.get(v), smap.get(v)) for v in verse_numbers]

def get_strong_entry(strong_number):
    with scripture_conn() as c:
        return c.execute("""
        SELECT strong_number,language,lemma,transliteration,pronunciation,definition,source
        FROM lexicon_entries WHERE strong_number=?
        """,(strong_number,)).fetchone()

def get_strong_occurrences(strong_number, translation_code=None, limit=250):
    with scripture_conn() as c:
        params=[strong_number]
        where=["sr.strong_number=?"]
        if translation_code:
            where.append("t.code=?")
            params.append(translation_code)
        params.append(limit)
        return c.execute(f"""
        SELECT
            t.code AS translation_code,
            b.name AS book,
            v.book_number,
            v.chapter,
            v.verse,
            v.text_clean,
            sr.tag_type,
            sr.occurrence
        FROM strong_refs sr
        JOIN verses v ON v.id=sr.verse_id
        JOIN translations t ON t.id=v.translation_id
        JOIN canonical_books b ON b.book_number=v.book_number
        WHERE {' AND '.join(where)}
        ORDER BY v.book_number,v.chapter,v.verse,sr.id
        LIMIT ?
        """, tuple(params)).fetchall()

def get_strong_translation_codes():
    with scripture_conn() as c:
        return c.execute("""
        SELECT code,name FROM translations
        WHERE edition_type='strongs'
        ORDER BY id
        """).fetchall()
