"""SQLite database (built into Python, nothing to install). Saves every analysis run:
sessions (one per run), events, and a summary of every tracked object. Snapshot pictures go in a folder next to it."""
import os
import sqlite3
import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY, source TEXT, started TEXT, duration_s REAL DEFAULT 0,
                                    frames INTEGER DEFAULT 0, vehicles INTEGER DEFAULT 0, pedestrians INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, session_id INTEGER, type TEXT, severity TEXT, objects TEXT,
                                  zone TEXT, frame INTEGER, time TEXT, x REAL, y REAL, details TEXT, status TEXT, snapshot TEXT);
CREATE TABLE IF NOT EXISTS tracks(session_id INTEGER, track_id INTEGER, class TEXT, first_frame INTEGER,
                                  last_frame INTEGER, avg_speed REAL, max_speed REAL);
CREATE INDEX IF NOT EXISTS events_session ON events(session_id);
"""
EVENT_COLUMNS = ("type", "severity", "objects", "zone", "frame", "time", "x", "y", "details", "status", "snapshot")


class Database:
    def __init__(self, path):
        self.root = os.path.dirname(os.path.abspath(path))
        self.snap_dir = os.path.join(self.root, "snapshots")
        os.makedirs(self.snap_dir, exist_ok=True)
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)

    def new_session(self, source):
        """Start a new run. Returns its id."""
        cur = self.con.execute("INSERT INTO sessions(source, started) VALUES(?, ?)",
                               (source, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
        self.con.commit()
        return cur.lastrowid

    def finish_session(self, sid, frames, duration_s, vehicles, pedestrians, tracks):
        """Save the totals and the per-object summary when a run ends. tracks = [(id, class, first, last, avg, max)]."""
        self.con.execute("UPDATE sessions SET frames=?, duration_s=?, vehicles=?, pedestrians=? WHERE id=?",
                         (frames, duration_s, vehicles, pedestrians, sid))
        self.con.execute("DELETE FROM tracks WHERE session_id=?", (sid,))
        self.con.executemany("INSERT INTO tracks VALUES(?, ?, ?, ?, ?, ?, ?)", [(sid, *t) for t in tracks])
        self.con.commit()

    def add_event(self, sid, ev):
        """Save one event. Returns its database id."""
        cur = self.con.execute(f"INSERT INTO events(session_id, {', '.join(EVENT_COLUMNS)}) VALUES(?{', ?' * len(EVENT_COLUMNS)})",
                               (sid, *[ev.get(c) for c in EVENT_COLUMNS]))
        self.con.commit()
        return cur.lastrowid

    def set_status(self, event_id, status):
        self.con.execute("UPDATE events SET status=? WHERE id=?", (status, event_id))
        self.con.commit()

    def sessions(self):
        """All saved runs, newest first, with their event counts."""
        return [dict(r) for r in self.con.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM events e WHERE e.session_id = s.id) AS n_events FROM sessions s ORDER BY s.id DESC")]

    def session(self, sid):
        row = self.con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        return dict(row) if row else None

    def events(self, sid):
        """Events of one run, oldest first, each with its database id as db_id."""
        out = []
        for r in self.con.execute("SELECT * FROM events WHERE session_id=? ORDER BY id", (sid,)):
            d = dict(r)
            d["db_id"] = d.pop("id")
            out.append(d)
        return out

    def tracks(self, sid):
        return [dict(r) for r in self.con.execute("SELECT * FROM tracks WHERE session_id=? ORDER BY track_id", (sid,))]

    def snapshot_path(self, relative):
        """Full path of a snapshot picture (saved as a short relative path), or None."""
        return os.path.join(self.root, relative) if relative else None
