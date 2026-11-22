"""Shared account scope for reports, qualification changes, help and pauses."""


def migrate(con):
    con.execute("""CREATE TABLE IF NOT EXISTS help_admin_config (
        id INTEGER PRIMARY KEY CHECK(id=1),
        admin_id TEXT NOT NULL REFERENCES access_principals(learner_id))""")
    columns = list(con.execute('PRAGMA table_info(help_admin_assignments)'))
    legacy = bool(columns) and sum(bool(row['pk']) for row in columns) == 1
    if legacy:
        con.execute('ALTER TABLE help_admin_assignments RENAME TO help_admin_assignments_legacy')
    con.execute("""CREATE TABLE IF NOT EXISTS help_admin_assignments (
        learner_id TEXT NOT NULL REFERENCES access_principals(learner_id),
        admin_id TEXT NOT NULL REFERENCES access_principals(learner_id),
        PRIMARY KEY(learner_id,admin_id))""")
    if legacy:
        con.execute("""INSERT INTO help_admin_assignments(learner_id,admin_id)
            SELECT learner_id,admin_id FROM help_admin_assignments_legacy""")
        con.execute('DROP TABLE help_admin_assignments_legacy')


def manager_ids(learner):
    """SQL for a trusted learner column or a bound parameter."""
    return f"""SELECT a.admin_id FROM help_admin_assignments a WHERE a.learner_id={learner}
        UNION ALL
        SELECT c.admin_id FROM help_admin_config c WHERE c.id=1 AND NOT EXISTS (
            SELECT 1 FROM help_admin_assignments a WHERE a.learner_id={learner})"""


def scope(learner):
    return f'? IN ({manager_ids(learner)})'


def includes(con, learner_id, admin_id):
    return con.execute(f"""SELECT 1 FROM access_principals p
        WHERE p.learner_id=? AND p.role='account' AND p.is_admin=0 AND {scope('p.learner_id')}""",
        (learner_id, admin_id)).fetchone() is not None
