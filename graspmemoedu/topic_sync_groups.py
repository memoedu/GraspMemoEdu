"""Course groups select a single baseline per learner and Topic."""

from contextlib import closing
import json

from .managed_accounts import includes
from .service import DomainError


GROUP_CONFLICT = 'topic_sync_group_conflict'
BASELINE_CONFLICT = 'topic_sync_baseline_conflict'


class TopicSyncGroups:
    def __init__(self, access_store, catalog):
        self.access_store = access_store
        self.catalog = catalog
        with closing(access_store._connect()) as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS topic_sync_groups (
                    group_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL REFERENCES access_principals(learner_id),
                    course_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    revision TEXT NOT NULL,
                    editable INTEGER NOT NULL CHECK (editable IN (0, 1)),
                    baselines TEXT NOT NULL,
                    UNIQUE (group_id, course_id));
                CREATE TABLE IF NOT EXISTS topic_sync_group_members (
                    learner_id TEXT NOT NULL REFERENCES access_principals(learner_id),
                    course_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    PRIMARY KEY (learner_id, course_id),
                    FOREIGN KEY (group_id, course_id) REFERENCES topic_sync_groups (group_id, course_id));
                CREATE INDEX IF NOT EXISTS topic_sync_members_by_group ON topic_sync_group_members(group_id);
                """)

    @staticmethod
    def _admin(access):
        if not access.get('is_admin'):
            raise DomainError('admin_required', '只有管理员可以管理课程分组。', 403)
        return access['learner_id']

    @staticmethod
    def _require_managed(con, learner_id, owner_id):
        if not includes(con, learner_id, owner_id):
            raise DomainError('student_forbidden', '此学员不在当前管理员的负责范围内。', 403)

    @staticmethod
    def _group(con, group_id, owner_id):
        row = con.execute('SELECT * FROM topic_sync_groups WHERE group_id=?', (group_id,)).fetchone()
        if not row or row['owner_id'] != owner_id:
            raise DomainError('topic_sync_group_unknown', '未找到此管理员的课程分组。', 404)
        return row

    @staticmethod
    def _public(row, members):
        return {key: row[key] for key in ('group_id', 'course_id', 'name', 'revision')} | {
            'editable': bool(row['editable']),
            'baselines': {topic: version for topic, version in json.loads(row['baselines']).items() if version},
            'members': list(members),
        }

    @staticmethod
    def _members(con, group_id):
        return [row['learner_id'] for row in con.execute('''SELECT learner_id
            FROM topic_sync_group_members WHERE group_id=? ORDER BY learner_id''', (group_id,))]

    def list(self, access):
        owner = self._admin(access)
        with closing(self.access_store._connect()) as con:
            groups = con.execute('SELECT * FROM topic_sync_groups WHERE owner_id=? ORDER BY course_id,name,group_id',
                                 (owner,)).fetchall()
            return [self._public(row, (learner for learner in self._members(con, row['group_id'])
                                       if includes(con, learner, owner))) for row in groups]

    def membership(self, access, learner_id, course_id):
        owner = self._admin(access)
        self.catalog.course(course_id)
        with closing(self.access_store._connect()) as con:
            self._require_managed(con, learner_id, owner)
            row = self._membership(con, learner_id, course_id)
            return {'group_id': row['group_id'], 'name': row['name']} if row else None

    @staticmethod
    def _membership(con, learner_id, course_id):
        return con.execute('''SELECT g.group_id,g.name FROM topic_sync_group_members m
            JOIN topic_sync_groups g USING (group_id,course_id)
            WHERE m.learner_id=? AND m.course_id=?''', (learner_id, course_id)).fetchone()

    def save_group(self, access, *, group_id, expected_revision, revision, course_id, name, editable, chosen):
        owner = self._admin(access)
        course = self.catalog.course(course_id)
        baselines = dict.fromkeys(row['id'] for row in course['topics'])
        if set(chosen) - baselines.keys():
            raise DomainError('topic_sync_baseline_course_mismatch', '基线含有其他课程的 Topic。', 422)
        baselines.update(chosen)
        serialized = json.dumps(baselines, sort_keys=True, separators=(',', ':'))
        with self.access_store._transaction() as con:
            current = con.execute('SELECT * FROM topic_sync_groups WHERE group_id=?', (group_id,)).fetchone()
            if current:
                current = self._group(con, group_id, owner)
                if current['course_id'] != course_id:
                    raise DomainError(GROUP_CONFLICT, '课程分组已经关联另一门课。', 409)
                if current['revision'] == revision:
                    if (current['name'], bool(current['editable']), current['baselines']) == (name, editable, serialized):
                        return self._public(current, (learner for learner in self._members(con, group_id)
                                                      if includes(con, learner, owner)))
                    raise DomainError(GROUP_CONFLICT, '分组保存标识已使用，请重新加载当前设置。', 409)
                if current['revision'] != expected_revision:
                    raise DomainError(GROUP_CONFLICT, '分组设置已有变化，原设置仍有效。请协调后再修改。', 409)
            elif expected_revision is not None:
                raise DomainError(GROUP_CONFLICT, '分组设置已有变化。请重新加载当前设置。', 409)
            for topic_id, version in chosen.items():
                self.access_store.authorize(access, topic_id)
                if not con.execute('''SELECT 1 FROM topic_sync_revisions
                    WHERE learner_id=? AND topic_id=? AND revision=?''', (owner, topic_id, version)).fetchone():
                    raise DomainError('topic_sync_baseline_unknown', '请选择自己已保存的 Topic 正文版本。', 422)
            members = self._members(con, group_id)
            for learner in members:
                self._require_managed(con, learner, owner)
                self._require_compatible(con, learner, owner, course_id, baselines)
            con.execute('''INSERT INTO topic_sync_groups VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_id) DO UPDATE SET name=excluded.name,revision=excluded.revision,
                    editable=excluded.editable,baselines=excluded.baselines''',
                (group_id, owner, course_id, name, revision, int(editable), serialized))
            return self._public(self._group(con, group_id, owner), members)

    def set_membership(self, access, *, learner_id, course_id, group_id, expected_group_id):
        owner = self._admin(access)
        self.catalog.course(course_id)
        with self.access_store._transaction() as con:
            self._require_managed(con, learner_id, owner)
            current = self._membership(con, learner_id, course_id)
            old_id = current['group_id'] if current else None
            group = self._group(con, group_id, owner) if group_id else None
            if group and group['course_id'] != course_id:
                raise DomainError(GROUP_CONFLICT, '此分组属于其他课程。', 409)
            if group_id == old_id:
                return {'group_id': group_id}
            if old_id != expected_group_id:
                raise DomainError(GROUP_CONFLICT, '此学员已有其他分组设置。请先与相关管理员协调。', 409)
            if group:
                self._require_compatible(con, learner_id, owner, course_id, json.loads(group['baselines']))
                con.execute('''INSERT INTO topic_sync_group_members VALUES (?, ?, ?)
                    ON CONFLICT(learner_id,course_id) DO UPDATE SET group_id=excluded.group_id''',
                    (learner_id, course_id, group_id))
            else:
                con.execute('DELETE FROM topic_sync_group_members WHERE learner_id=? AND course_id=?',
                            (learner_id, course_id))
        return {'group_id': group_id}

    @staticmethod
    def _groups_for(con, learner_id):
        return con.execute('''SELECT g.owner_id,g.course_id,g.baselines,g.editable FROM topic_sync_group_members m
            JOIN topic_sync_groups g USING (group_id,course_id) WHERE m.learner_id=? ORDER BY g.course_id''',
            (learner_id,)).fetchall()

    @staticmethod
    def _reference(owner, version):
        return (owner, version) if version else (None, None)

    def _require_compatible(self, con, learner_id, owner, course_id, baselines):
        for group in self._groups_for(con, learner_id):
            other_course = group['course_id']
            if other_course == course_id or other_course not in self.catalog.courses:
                continue
            other = json.loads(group['baselines'])
            for topic_id in sorted(baselines.keys() & other.keys()):
                memberships = self.catalog.topic_courses.get(topic_id, ())
                if other_course in memberships and course_id in memberships and (
                    self._reference(owner, baselines[topic_id]) != self._reference(group['owner_id'], other[topic_id])
                ):
                    raise DomainError(BASELINE_CONFLICT,
                                      f'共享 Topic {topic_id} 已有不同基线。原分组设置仍有效，请管理员协调后重新分配。', 409)

    def topic_policy(self, con, learner_id, topic_id):
        result = (None, None)
        editable = True
        courses = self.catalog.topic_courses[topic_id]
        for group in self._groups_for(con, learner_id):
            if group['course_id'] not in courses:
                continue
            editable = editable and bool(group['editable'])
            baselines = json.loads(group['baselines'])
            if topic_id in baselines:
                result = self._reference(group['owner_id'], baselines[topic_id])
        return result[0], result[1], editable
