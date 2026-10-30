import sqlite3

conn = sqlite3.connect('reestack.db')
cur = conn.cursor()
cur.execute('PRAGMA table_info(users)')
cols = [r[1] for r in cur.fetchall()]
for c in ['display_name','bio','avatar_url']:
    if c not in cols:
        cur.execute(f'ALTER TABLE users ADD COLUMN {c} TEXT')
conn.commit()
conn.close()
print('done')
