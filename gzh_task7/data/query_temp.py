import json, sqlite3
from pathlib import Path
db = Path('data') / 'sample.db'
conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT * FROM employees ORDER BY salary DESC LIMIT 3')
rows = [dict(r) for r in cur.fetchall()]
conn.close()
print(json.dumps({'success': True, 'count': len(rows), 'rows': rows}, ensure_ascii=False, indent=2))
