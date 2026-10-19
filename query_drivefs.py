import sqlite3
import shutil
import os

db_path = os.path.expandvars(r'%LOCALAPPDATA%\Google\DriveFS\105350898700926971018\mirror_metadata_sqlite.db')
temp_db = 'temp_drive_meta.db'

try:
    shutil.copy2(db_path, temp_db)
    if os.path.exists(db_path + '-wal'):
        shutil.copy2(db_path + '-wal', temp_db + '-wal')

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cursor.fetchall()]
    print('Tables in DB:', tables)

    folder_id = '16FgmNLjjcwXP42mUji6upaAmKOlwYJwJ'

    found = False
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [c[1] for c in cursor.fetchall()]
        for col in columns:
            try:
                cursor.execute(f"SELECT * FROM {table} WHERE {col} = ?", (folder_id,))
                rows = cursor.fetchall()
                if rows:
                    print(f"\n[FOUND!] Table: {table}, Column: {col}")
                    for r in rows:
                        print("Row:", r)
                    found = True
            except Exception:
                pass

    if not found:
        print("\nNot found by exact ID. Searching like pattern...")
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [c[1] for c in cursor.fetchall()]
            for col in columns:
                try:
                    cursor.execute(f"SELECT * FROM {table} WHERE {col} LIKE ?", (f"%{folder_id}%",))
                    rows = cursor.fetchall()
                    if rows:
                        print(f"[LIKE MATCH] Table: {table}, Col: {col}, Count: {len(rows)}")
                except Exception:
                    pass

    conn.close()
finally:
    for f in [temp_db, temp_db + '-wal']:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass
