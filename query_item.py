import sqlite3
import shutil
import os
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

db_path = os.path.expandvars(r'%LOCALAPPDATA%\Google\DriveFS\105350898700926971018\mirror_metadata_sqlite.db')
temp_db = 'temp_drive_meta.db'

try:
    shutil.copy2(db_path, temp_db)
    if os.path.exists(db_path + '-wal'):
        shutil.copy2(db_path + '-wal', temp_db + '-wal')

    conn = sqlite3.connect(temp_db)
    conn.text_factory = bytes
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM items WHERE stable_id=6684;")
    rows = cursor.fetchall()
    cursor.execute("PRAGMA table_info(items);")
    cols = [c[1].decode('utf-8', errors='ignore') for c in cursor.fetchall()]

    for r in rows:
        print("Item details:")
        for col_name, val in zip(cols, r):
            if isinstance(val, bytes):
                # decode utf-8 or print representation
                try:
                    decoded = val.decode('utf-8')
                    print(f"  {col_name}: {decoded}")
                except Exception:
                    # 바이너리에서 문자열 추출
                    strings = [s.decode('utf-8', errors='ignore') for s in val.split(b'\x00') if len(s) > 2]
                    print(f"  {col_name} (bytes): {val[:100]} | strings: {strings[:5]}")
            else:
                print(f"  {col_name}: {val}")

    conn.close()
finally:
    for f in [temp_db, temp_db + '-wal']:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass
