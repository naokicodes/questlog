CREATE VIRTUAL TABLE IF NOT EXISTS journal_fts USING fts5(
    title, body_md, content='journal_entries', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS journal_ai AFTER INSERT ON journal_entries BEGIN
    INSERT INTO journal_fts(rowid, title, body_md) VALUES (new.id, new.title, new.body_md);
END;

CREATE TRIGGER IF NOT EXISTS journal_ad AFTER DELETE ON journal_entries BEGIN
    INSERT INTO journal_fts(journal_fts, rowid, title, body_md)
    VALUES ('delete', old.id, old.title, old.body_md);
END;

CREATE TRIGGER IF NOT EXISTS journal_au AFTER UPDATE ON journal_entries BEGIN
    INSERT INTO journal_fts(journal_fts, rowid, title, body_md)
    VALUES ('delete', old.id, old.title, old.body_md);
    INSERT INTO journal_fts(rowid, title, body_md) VALUES (new.id, new.title, new.body_md);
END;
