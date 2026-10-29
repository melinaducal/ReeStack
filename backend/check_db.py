import sqlite3

conn = sqlite3.connect('reestack.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('TABLES:', tables)

for t in ['users', 'items', 'comments', 'likes']:
    try:
        cur.execute(f'SELECT COUNT(*) FROM {t}')
        print(f'{t}:', cur.fetchone()[0])
    except Exception as e:
        print(f'{t}: ERR', e)

conn.close()
print('DB PATH: reestack.db (relative to backend/)')
