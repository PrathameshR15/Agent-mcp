import sqlite3
import json
import os

class SimpleDB:
    def __init__(self, db_path="mcp.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS agents (id TEXT PRIMARY KEY, data TEXT)")
        self.conn.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, data TEXT)")
        self.conn.commit()

    def save_agent(self, agent_id, data):
        self.conn.execute("INSERT OR REPLACE INTO agents (id, data) VALUES (?, ?)", (agent_id, json.dumps(data)))
        self.conn.commit()
        
    def delete_agent(self, agent_id):
        self.conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
        self.conn.commit()

    def get_all_agents(self):
        return {row[0]: json.loads(row[1]) for row in self.conn.execute("SELECT id, data FROM agents")}

    def save_job(self, job_id, data):
        self.conn.execute("INSERT OR REPLACE INTO jobs (id, data) VALUES (?, ?)", (job_id, json.dumps(data)))
        self.conn.commit()

    def get_all_jobs(self):
        return {row[0]: json.loads(row[1]) for row in self.conn.execute("SELECT id, data FROM jobs")}

db = SimpleDB()
