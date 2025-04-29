import sqlite3
import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# -----------------------------
# Database Layer
# -----------------------------
class Database:
    def __init__(self, db_path='channels.db'):
        # Включаем внешние ключи для каскадного удаления
        self.conn = sqlite3.connect(db_path)
        self.conn.execute('PRAGMA foreign_keys = ON')
        self._create_tables()

    def _create_tables(self):
        """Создает необходимые таблицы при первом запуске"""
        cursor = self.conn.cursor()
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            url TEXT UNIQUE NOT NULL,
            post_times TEXT,
            forbidden_words TEXT
        );
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            source_url TEXT NOT NULL,
            parse_media INTEGER NOT NULL,
            forbidden_words TEXT,
            FOREIGN KEY(channel_id) REFERENCES channels(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            site_url TEXT NOT NULL,
            site_type TEXT CHECK(site_type IN ('AUTO','RENT','BUY','FREE')) NOT NULL,
            FOREIGN KEY(channel_id) REFERENCES sources(id) ON DELETE CASCADE
        );
        """
        )
        self.conn.commit()

    def _execute(self, query, params=None, fetch=False):
        """Упрощённый метод выполнения запросов"""
        cur = self.conn.cursor()
        cur.execute(query, params or ())
        if fetch:
            return cur.fetchall()
        self.conn.commit()
        return None

    # Channels CRUD
    def list_channels(self):
        return self._execute("SELECT * FROM channels", fetch=True)

    def create_channel(self, name, url, post_times, forbidden_words):
        self._execute(
            "INSERT INTO channels(name,url,post_times,forbidden_words) VALUES (?,?,?,?)",
            (name, url, json.dumps(post_times), json.dumps(forbidden_words))
        )

    def update_channel(self, cid, name, url, post_times, forbidden_words):
        self._execute(
            "UPDATE channels SET name=?,url=?,post_times=?,forbidden_words=? WHERE id=?",
            (name, url, json.dumps(post_times), json.dumps(forbidden_words), cid)
        )

    def delete_channel(self, cid):
        self._execute("DELETE FROM channels WHERE id=?", (cid,))

    # Sources CRUD
    def list_sources(self):
        return self._execute("SELECT * FROM sources", fetch=True)

    def create_source(self, channel_id, url, parse_media, forbidden_words):
        self._execute(
            "INSERT INTO sources(channel_id,source_url,parse_media,forbidden_words) VALUES(?,?,?,?)",
            (channel_id, url, int(parse_media), json.dumps(forbidden_words))
        )

    def update_source(self, sid, channel_id, url, parse_media, forbidden_words):
        self._execute(
            "UPDATE sources SET channel_id=?,source_url=?,parse_media=?,forbidden_words=? WHERE id=?",
            (channel_id, url, int(parse_media), json.dumps(forbidden_words), sid)
        )

    def delete_source(self, sid):
        self._execute("DELETE FROM sources WHERE id=?", (sid,))

    # Sites CRUD
    def list_sites(self):
        return self._execute("SELECT * FROM sites", fetch=True)

    def create_site(self, source_id, site_url, site_type):
        self._execute(
            "INSERT INTO sites(channel_id,site_url,site_type) VALUES(?,?,?)",
            (source_id, site_url, site_type)
        )

    def update_site(self, tid, source_id, site_url, site_type):
        self._execute(
            "UPDATE sites SET channel_id=?,site_url=?,site_type=? WHERE id=?",
            (source_id, site_url, site_type, tid)
        )

    def delete_site(self, tid):
        self._execute("DELETE FROM sites WHERE id=?", (tid,))


# -----------------------------
# UI Layer
# -----------------------------
class App(tk.Tk):
    def __init__(self, db: Database):
        super().__init__()
        self.title("SQLite Manager")
        self.geometry("900x600")
        self.db = db
        self._build_ui()

    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True)

        self.frames = {}
        for label, methods in [
            ("Channels", (self.db.list_channels, self.db.create_channel, self.db.update_channel, self.db.delete_channel)),
            ("Sources",  (self.db.list_sources, self.db.create_source, self.db.update_source, self.db.delete_source)),
            ("Sites",    (self.db.list_sites, self.db.create_site, self.db.update_site, self.db.delete_site)),
        ]:
            frame = TableFrame(nb, label.lower(), methods)
            nb.add(frame, text=label)
            self.frames[label.lower()] = frame


class TableFrame(ttk.Frame):
    def __init__(self, parent, name, methods):
        super().__init__(parent)
        self.name = name
        self.list_fn, self.add_fn, self.upd_fn, self.del_fn = methods

        cols = self._columns_map()[name]
        self.tree = ttk.Treeview(self, columns=cols, show='headings')
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.pack(fill=tk.BOTH, expand=True)

        btns = ttk.Frame(self)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Add",    command=self._on_add).pack(side=tk.LEFT)
        ttk.Button(btns, text="Edit",   command=self._on_edit).pack(side=tk.LEFT)
        ttk.Button(btns, text="Delete", command=self._on_delete).pack(side=tk.LEFT)

        self.refresh()

    def _columns_map(self):
        return {
            'channels': ['id','name','url','post_times','forbidden_words'],
            'sources':  ['id','channel_id','source_url','parse_media','forbidden_words'],
            'sites':    ['id','channel_id','site_url','site_type'],
        }

    def refresh(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for row in self.list_fn():
            vals = list(row)
            if self.name == 'channels':
                vals[3] = ','.join(json.loads(vals[3] or '[]'))
                vals[4] = ','.join(json.loads(vals[4] or '[]'))
            if self.name == 'sources':
                vals[3] = 'Yes' if vals[3] else 'No'
                vals[4] = ','.join(json.loads(vals[4] or '[]'))
            self.tree.insert('', tk.END, values=vals)

    def _get_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select row", "Please select a row.")
            return None
        return self.tree.item(sel[0])['values']

    def _on_add(self):
        data = self._prompt_fields()
        if not data: return
        self.add_fn(*data)
        self.refresh()

    def _on_edit(self):
        rec = self._get_selected()
        if not rec: return
        data = self._prompt_fields(rec)
        if not data: return
        self.upd_fn(rec[0], *data)
        self.refresh()

    def _on_delete(self):
        rec = self._get_selected()
        if not rec: return
        if messagebox.askyesno("Confirm", f"Delete ID={rec[0]}? This cascades."):
            self.del_fn(rec[0])
            self.refresh()

    def _prompt_fields(self, record=None):
        prompts = {
            'channels': ['Name','URL','Post times (comma sep)','Forbidden words (comma sep)'],
            'sources':  ['Channel ID','Source URL','Parse media (True/False)','Forbidden words'],
            'sites':    ['Source ID','Site URL','Site type (AUTO/RENT/BUY/FREE)'],
        }[self.name]
        values = []
        for i, prompt in enumerate(prompts):
            default = record[i+1] if record else ''
            val = simpledialog.askstring("Input", prompt, initialvalue=default, parent=self)
            if val is None: return None
            values.append(val)
        # post-process lists and flags
        if self.name == 'channels':
            return [values[0], values[1], [t.strip() for t in values[2].split(',') if t.strip()], [w.strip() for w in values[3].split(',') if w.strip()]]
        if self.name == 'sources':
            return [int(values[0]), values[1], values[2].lower() in ('true','1','yes'), [w.strip() for w in values[3].split(',') if w.strip()]]
        return [int(values[0]), values[1], values[2]]


if __name__ == '__main__':
    db = Database()
    App(db).mainloop()
