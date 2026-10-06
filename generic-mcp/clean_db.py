import sqlite3
conn = sqlite3.connect('mcp.db')
conn.execute("DELETE FROM agents WHERE id != 'local-predict-agent-01'")
conn.commit()
