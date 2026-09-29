#!/usr/bin/env python3
from __future__ import annotations
import argparse,re,sqlite3
from pathlib import Path
from collections import OrderedDict

BOOKS=["Genesis","Exodus","Leviticus","Numbers","Deuteronomy","Joshua","Judges","Ruth","1 Samuel","2 Samuel","1 Kings","2 Kings","1 Chronicles","2 Chronicles","Ezra","Nehemiah","Esther","Job","Psalms","Proverbs","Ecclesiastes","Song of Solomon","Isaiah","Jeremiah","Lamentations","Ezekiel","Daniel","Hosea","Joel","Amos","Obadiah","Jonah","Micah","Nahum","Habakkuk","Zephaniah","Haggai","Zechariah","Malachi","Matthew","Mark","Luke","John","Acts","Romans","1 Corinthians","2 Corinthians","Galatians","Ephesians","Philippians","Colossians","1 Thessalonians","2 Thessalonians","1 Timothy","2 Timothy","Titus","Philemon","Hebrews","James","1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation"]
BN={b:i+1 for i,b in enumerate(BOOKS)}
ALIASES={"Psalm":"Psalms","Song of Songs":"Song of Solomon","Canticles":"Song of Solomon","Revelation of John":"Revelation","The Revelation":"Revelation"}
TAG=re.compile(r'\{(\(?[HG]\d+\)?)\}')

def parse(path):
    lines=path.read_text(encoding="utf-8-sig",errors="replace").splitlines()
    chunks=[];book=None;chapter=None;verse=None;buf=[]
    def flush():
        nonlocal verse,buf
        if book and chapter and verse is not None:
            chunks.append((BN[book],chapter,verse,re.sub(r'\s+',' '," ".join(buf)).strip()))
        verse=None;buf=[]
    for raw in lines:
        s=raw.strip()
        if not s:continue
        cand=ALIASES.get(s,s)
        if cand in BN:
            flush();book=cand;chapter=None;continue
        m=re.match(r'^(?:Chapter|Psalm)\s+(\d+)\s*$',s,re.I)
        if m and book:
            flush();chapter=int(m.group(1));continue
        if book and chapter:
            m=re.match(r'^(\d+)\s+(.*)$',s)
            if m:
                flush();verse=int(m.group(1));buf=[m.group(2)]
            elif verse is not None:
                buf.append(s)
    flush()
    merged=OrderedDict()
    for b,c,v,t in chunks:
        k=(b,c,v);merged[k]=(merged.get(k,"")+" "+t).strip()
    return [(b,c,v,t) for (b,c,v),t in merged.items()]

def main():
    a=argparse.ArgumentParser(description="Universal Scripture Notes translation importer")
    a.add_argument("file",type=Path)
    a.add_argument("--code",required=True)
    a.add_argument("--name",required=True)
    a.add_argument("--rights",default="")
    a.add_argument("--base-code")
    a.add_argument("--local-only",action="store_true")
    a.add_argument("--db",type=Path,default=Path("data/bible.db"))
    args=a.parse_args()
    code=args.code.upper()
    verses=parse(args.file)
    if not verses:raise SystemExit("No verses parsed.")
    strongs=any(TAG.search(t) for *_,t in verses)
    edition="strongs" if strongs else "standard"
    conn=sqlite3.connect(args.db)
    conn.row_factory=sqlite3.Row
    if conn.execute("SELECT 1 FROM translations WHERE code=?",(code,)).fetchone():
        raise SystemExit(f"{code} already exists.")
    books=len(set(x[0] for x in verses))
    cur=conn.execute("""INSERT INTO translations(code,name,language,edition_type,base_code,rights,source_filename,redistributable,is_complete)
    VALUES(?,?,?,?,?,?,?,?,?)""",(code,args.name,"English",edition,args.base_code,args.rights,args.file.name,0 if args.local_only else 1,1 if books==66 else 0))
    tid=cur.lastrowid
    for b,c,v,raw in verses:
        clean=TAG.sub("",raw)
        vid=conn.execute("""INSERT INTO verses(translation_id,book_number,chapter,verse,text_raw,text_clean)
        VALUES(?,?,?,?,?,?)""",(tid,b,c,v,raw,clean)).lastrowid
        occ={}
        for m in TAG.finditer(raw):
            token=m.group(1);num=token.strip("()");occ[num]=occ.get(num,0)+1
            conn.execute("INSERT INTO strong_refs(verse_id,strong_number,tag_type,occurrence) VALUES(?,?,?,?)",
                         (vid,num,"morphology" if token.startswith("(") else "lexeme",occ[num]))
        conn.execute("INSERT INTO verse_fts(rowid,translation_id,book_number,chapter,verse,text_clean) VALUES(?,?,?,?,?,?)",
                     (vid,tid,b,c,v,clean))
    conn.commit();conn.close()
    print(f"Imported {args.name} ({code}): {len(verses)} verses, {books} books, type={edition}")

if __name__=="__main__":main()
