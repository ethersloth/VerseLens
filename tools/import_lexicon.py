#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,sqlite3
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description="Import Strong's lexicon entries from CSV/TSV.")
    ap.add_argument("file",type=Path)
    ap.add_argument("--db",type=Path,default=Path("data/bible.db"))
    ap.add_argument("--delimiter",default=None,help="Optional delimiter override, e.g. ',' or '\\t'")
    ap.add_argument("--source",default="")
    args=ap.parse_args()

    sample=args.file.read_text(encoding="utf-8-sig",errors="replace")[:4096]
    delim=args.delimiter
    if not delim:
        delim="\\t" if "\\t" in sample else ","

    con=sqlite3.connect(args.db)
    con.execute("""
    CREATE TABLE IF NOT EXISTS lexicon_entries(
        strong_number TEXT PRIMARY KEY,
        language TEXT,
        lemma TEXT,
        transliteration TEXT,
        pronunciation TEXT,
        definition TEXT,
        source TEXT
    )
    """)

    count=0
    with args.file.open("r",encoding="utf-8-sig",errors="replace",newline="") as f:
        reader=csv.DictReader(f,delimiter=delim)
        for row in reader:
            num=(row.get("strong_number") or row.get("strong") or row.get("number") or "").strip()
            if not num:
                continue
            con.execute("""
            INSERT INTO lexicon_entries(
                strong_number,language,lemma,transliteration,pronunciation,definition,source
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(strong_number) DO UPDATE SET
                language=excluded.language,
                lemma=excluded.lemma,
                transliteration=excluded.transliteration,
                pronunciation=excluded.pronunciation,
                definition=excluded.definition,
                source=excluded.source
            """,(
                num,
                (row.get("language") or "").strip(),
                (row.get("lemma") or "").strip(),
                (row.get("transliteration") or "").strip(),
                (row.get("pronunciation") or "").strip(),
                (row.get("definition") or row.get("meaning") or "").strip(),
                args.source or args.file.name
            ))
            count+=1
    con.commit()
    con.close()
    print(f"Imported {count} lexicon entries.")

if __name__=="__main__":
    main()
