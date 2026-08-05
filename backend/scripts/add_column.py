import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import sqlite3

db_path = os.path.join(os.path.dirname(__file__), '..', 'test_platform', 'backend', 'data', 'test_platform.db')
conn = sqlite3.connect(db_path)
try:
    conn.execute('ALTER TABLE runs ADD COLUMN name TEXT DEFAULT ""')
    conn.commit()
    print('Column added successfully')
except sqlite3.OperationalError as e:
    if 'duplicate column name' in str(e):
        print('Column already exists')
    else:
        raise
finally:
    conn.close()