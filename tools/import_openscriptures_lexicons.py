#!/usr/bin/env python3
from __future__ import annotations
import argparse
import html
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

def ensure_schema(conn):
    conn.execute("""
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
    conn.commit()

def normalize_num(prefix, value):
    s=str(value).strip()
    s=re.sub(r'^[HGhg]','',s)
    s=re.sub(r'\D','',s)
    if not s:
        return None
    return f"{prefix.upper()}{int(s)}"

def text_content(elem):
    return re.sub(r'\s+',' ',' '.join(''.join(elem.itertext()).split())).strip()

def import_unified_xhtml(conn, path: Path):
    """Import openscriptures/strongs strongs-dictionary.xhtml."""
    tree=ET.parse(path)
    root=tree.getroot()
    count=0
    for li in root.iter():
        tag=li.tag.rsplit('}',1)[-1]
        if tag != 'li':
            continue
        ident=li.attrib.get('id','')
        m=re.fullmatch(r'(ot|nt):(\d+)', ident)
        if not m:
            continue
        prefix='H' if m.group(1)=='ot' else 'G'
        num=normalize_num(prefix,m.group(2))
        if not num:
            continue
        language='Hebrew' if prefix=='H' else 'Greek'
        first_i=None
        for child in li.iter():
            if child.tag.rsplit('}',1)[-1]=='i':
                first_i=child
                break
        lemma=(text_content(first_i) if first_i is not None else '')
        pronunciation=(first_i.attrib.get('title','') if first_i is not None else '')
        definition=text_content(li)
        conn.execute("""
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
        """,(num,language,lemma,lemma,pronunciation,definition,
             "Open Scriptures Strong's Dictionaries"))
        count+=1
    conn.commit()
    return count

def import_js_dictionary(conn, path: Path, prefix: str):
    """
    Import Open Scriptures generated JS dictionaries.
    Handles CommonJS wrappers and common field names used by generated Strong's datasets.
    """
    raw=path.read_text(encoding='utf-8-sig',errors='replace')
    # Strip common module wrappers and locate the largest JSON-like object.
    start=raw.find('{')
    end=raw.rfind('}')
    if start < 0 or end <= start:
        raise ValueError(f"Could not locate dictionary object in {path}")
    body=raw[start:end+1]

    # Convert a conservative subset of JS object syntax to JSON.
    body=re.sub(r'(?m)^\s*//.*$','',body)
    body=re.sub(r'/\*.*?\*/','',body,flags=re.S)
    body=re.sub(r'([{,]\s*)([A-Za-z_$][\w$]*)(\s*:)',r'\1"\2"\3',body)
    body=body.replace("'", '"')
    body=re.sub(r',\s*([}\]])',r'\1',body)

    data=json.loads(body)
    count=0
    for key,val in data.items():
        if not isinstance(val,dict):
            continue
        num=normalize_num(prefix,key)
        if not num:
            continue
        language='Hebrew' if prefix.upper()=='H' else 'Greek'
        lemma=str(val.get('lemma') or val.get('word') or val.get('greek') or val.get('hebrew') or '').strip()
        translit=str(val.get('translit') or val.get('xlit') or val.get('transliteration') or '').strip()
        pron=str(val.get('pron') or val.get('pronunciation') or '').strip()
        definition=str(
            val.get('definition') or val.get('description') or
            val.get('strongs_def') or val.get('kjv_def') or ''
        ).strip()
        conn.execute("""
        INSERT INTO lexicon_entries(
            strong_number,language,lemma,transliteration,pronunciation,definition,source
        ) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(strong_number) DO UPDATE SET
            language=excluded.language,
            lemma=CASE WHEN excluded.lemma<>'' THEN excluded.lemma ELSE lexicon_entries.lemma END,
            transliteration=CASE WHEN excluded.transliteration<>'' THEN excluded.transliteration ELSE lexicon_entries.transliteration END,
            pronunciation=CASE WHEN excluded.pronunciation<>'' THEN excluded.pronunciation ELSE lexicon_entries.pronunciation END,
            definition=CASE WHEN excluded.definition<>'' THEN excluded.definition ELSE lexicon_entries.definition END,
            source=excluded.source
        """,(num,language,lemma,translit,pron,definition,
             f"Open Scriptures Strong's {language} dictionary"))
        count+=1
    conn.commit()
    return count

def import_hebrew_xml(conn, path: Path):
    """
    Best-effort importer for openscriptures/HebrewLexicon HebrewStrong.xml.
    Uses entry IDs/Strong numbers plus visible XML text so it remains useful
    even when the XML schema evolves.
    """
    tree=ET.parse(path)
    root=tree.getroot()
    count=0
    for elem in root.iter():
        attrs={k.rsplit('}',1)[-1]:v for k,v in elem.attrib.items()}
        candidate=attrs.get('id') or attrs.get('strong') or attrs.get('number') or ''
        m=re.search(r'(\d+)',candidate)
        if not m:
            continue
        tag=elem.tag.rsplit('}',1)[-1].lower()
        if 'entry' not in tag and 'lex' not in tag:
            continue
        num=normalize_num('H',m.group(1))
        content=text_content(elem)
        if not content:
            continue
        conn.execute("""
        INSERT INTO lexicon_entries(
            strong_number,language,lemma,transliteration,pronunciation,definition,source
        ) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(strong_number) DO UPDATE SET
            definition=CASE
              WHEN length(excluded.definition)>length(lexicon_entries.definition)
              THEN excluded.definition ELSE lexicon_entries.definition END,
            source=lexicon_entries.source || '; Open Scriptures HebrewLexicon'
        """,(num,'Hebrew','','','',content,'Open Scriptures HebrewLexicon'))
        count+=1
    conn.commit()
    return count

def main():
    ap=argparse.ArgumentParser(
        description="Import Open Scriptures Strong's and HebrewLexicon repositories."
    )
    ap.add_argument("--strongs-repo",type=Path,
                    help="Path to a clone of openscriptures/strongs")
    ap.add_argument("--hebrew-lexicon-repo",type=Path,
                    help="Path to a clone of openscriptures/HebrewLexicon")
    ap.add_argument("--db",type=Path,default=Path("data/bible.db"))
    args=ap.parse_args()

    if not args.strongs_repo and not args.hebrew_lexicon_repo:
        raise SystemExit("Provide --strongs-repo and/or --hebrew-lexicon-repo")

    conn=sqlite3.connect(args.db)
    ensure_schema(conn)
    total=0

    if args.strongs_repo:
        repo=args.strongs_repo
        xhtml=repo/"strongs-dictionary.xhtml"
        if xhtml.exists():
            n=import_unified_xhtml(conn,xhtml)
            total+=n
            print(f"Imported {n} entries from {xhtml}")
        else:
            g=repo/"greek"/"strongs-greek-dictionary.js"
            h=repo/"hebrew"/"strongs-hebrew-dictionary.js"
            if g.exists():
                n=import_js_dictionary(conn,g,'G'); total+=n
                print(f"Imported {n} Greek entries from {g}")
            if h.exists():
                n=import_js_dictionary(conn,h,'H'); total+=n
                print(f"Imported {n} Hebrew entries from {h}")

    if args.hebrew_lexicon_repo:
        repo=args.hebrew_lexicon_repo
        hs=repo/"HebrewStrong.xml"
        if hs.exists():
            n=import_hebrew_xml(conn,hs)
            total+=n
            print(f"Imported/augmented {n} Hebrew entries from {hs}")
        else:
            print(f"Warning: {hs} not found")

    conn.close()
    print(f"Done. Processed {total} lexicon entries.")

if __name__=="__main__":
    main()
