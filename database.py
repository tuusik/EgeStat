import json
import logging
import os
import re
import sqlite3

import pandas as pd

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.getcwd(), 'ege_stat.db')
FILES_DIR = os.path.join(os.getcwd(), 'files')

ORDER_COLUMNS = {'avg_primary', 'avg_secondary'}


class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        return self

    def __exit__(self, *args):
        if self.conn:
            self.conn.close()
            self.conn = None

    def cursor(self):
        return self.conn.cursor()

    def commit(self):
        self.conn.commit()

    # ---- queries ----

    def get_students_pivot_data(self):
        return pd.read_sql_query('''
            SELECT s.name, v.name as variant_name,
                   s.primary_score, s.secondary_score
            FROM students s
            JOIN variants v ON s.variant_id = v.id
        ''', self.conn)

    def get_variants(self):
        return pd.read_sql_query(
            'SELECT id, name FROM variants ORDER BY name', self.conn
        )

    def get_student_names(self):
        return pd.read_sql_query(
            'SELECT DISTINCT name FROM students ORDER BY name', self.conn
        )

    def get_existing_variant_names(self):
        cursor = self.cursor()
        cursor.execute('SELECT name FROM variants')
        names = {r[0] for r in cursor.fetchall()}
        logger.debug("get_existing_variant_names: %d names", len(names))
        return names

    def get_task_stats(self):
        return pd.read_sql_query('''
            SELECT r.number as task_number,
                   ROUND(CAST(SUM(r.score) AS FLOAT) / COUNT(*) * 100, 1) as solve_rate
            FROM results r
            GROUP BY r.number
            ORDER BY r.number ASC
        ''', self.conn)

    def get_student_avg(self, order_col='avg_primary'):
        if order_col not in ORDER_COLUMNS:
            order_col = 'avg_primary'
        return pd.read_sql_query(f'''
            SELECT s.name,
                   ROUND(AVG(s.primary_score), 1) as avg_primary,
                   ROUND(AVG(s.secondary_score), 1) as avg_secondary,
                   COUNT(*) as tests_count
            FROM students s
            GROUP BY s.name
            ORDER BY {order_col} DESC
        ''', self.conn)

    def get_student_task_analysis(self, name):
        return pd.read_sql_query('''
            SELECT r.number as task_number,
                   ROUND(CAST(SUM(r.score) AS FLOAT) / COUNT(*) * 100, 1) as solve_rate
            FROM results r
            JOIN students s ON r.student_id = s.id
            WHERE s.name = ?
            GROUP BY r.number
            ORDER BY r.number ASC
        ''', self.conn, params=(name,))

    def delete_variant(self, variant_id):
        cursor = self.cursor()
        cursor.execute(
            'DELETE FROM results WHERE student_id IN '
            '(SELECT id FROM students WHERE variant_id = ?)',
            (variant_id,)
        )
        cursor.execute('DELETE FROM students WHERE variant_id = ?', (variant_id,))
        cursor.execute('DELETE FROM variants WHERE id = ?', (variant_id,))
        logger.info("Deleted variant id=%d", variant_id)

    def delete_student(self, name):
        cursor = self.cursor()
        cursor.execute(
            'DELETE FROM results WHERE student_id IN '
            '(SELECT id FROM students WHERE name = ?)',
            (name,)
        )
        cursor.execute('DELETE FROM students WHERE name = ?', (name,))
        logger.info("Deleted student '%s'", name)

    def target_name_exists(self, name):
        cursor = self.cursor()
        cursor.execute('SELECT COUNT(*) FROM students WHERE name = ?', (name,))
        row = cursor.fetchone()
        return row is not None and row[0] > 0

    def get_student_variants(self, name):
        cursor = self.cursor()
        cursor.execute('SELECT DISTINCT variant_id FROM students WHERE name = ?', (name,))
        return {r[0] for r in cursor.fetchall()}

    def get_student_scores_by_variant(self, name, variant_id):
        cursor = self.cursor()
        cursor.execute(
            'SELECT id, primary_score FROM students WHERE name = ? AND variant_id = ?',
            (name, variant_id)
        )
        return cursor.fetchall()

    def delete_student_by_ids(self, ids):
        cursor = self.cursor()
        for sid in ids:
            cursor.execute('DELETE FROM results WHERE student_id = ?', (sid,))
            cursor.execute('DELETE FROM students WHERE id = ?', (sid,))

    def rename_student_simple(self, old_name, new_name):
        cursor = self.cursor()
        cursor.execute('UPDATE students SET name = ? WHERE name = ?', (new_name, old_name))
        logger.info("Renamed student '%s' -> '%s'", old_name, new_name)

    def rename_variant(self, variant_id, new_name):
        cursor = self.cursor()
        cursor.execute('UPDATE variants SET name = ? WHERE id = ?', (new_name, variant_id))
        logger.info("Renamed variant id=%d -> '%s'", variant_id, new_name)

    def get_or_create_variant(self, name, kim):
        cursor = self.cursor()
        cursor.execute('SELECT id FROM variants WHERE name = ?', (name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute(
            'INSERT INTO variants (name, kim) VALUES (?, ?)',
            (name, kim)
        )
        vid = cursor.lastrowid
        logger.debug("Created variant id=%d name='%s'", vid, name)
        return vid

    def insert_student(self, rec, variant_id):
        cursor = self.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO students
                (id, name, user_id, variant_id, primary_score,
                 secondary_score, duration, hide, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            rec['id'], rec['name'], rec.get('user_id'), variant_id,
            rec.get('primaryScore'), rec.get('secondaryScore'),
            rec.get('duration'),
            1 if rec.get('hide') else 0,
            rec.get('createdAt'), rec.get('updatedAt')
        ))

    def insert_result(self, student_id, r):
        cursor = self.cursor()
        cursor.execute('''
            INSERT INTO results
                (student_id, key, score, answer, number, task_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            student_id, r.get('key'), r.get('score'),
            r.get('answer'), r.get('number'), r.get('taskId')
        ))

    def load_json_file(self, filename, variant_name):
        filepath = os.path.join(FILES_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            records = json.load(f)

        if not records:
            return 0

        kim = records[0].get('kim')
        variant_id = self.get_or_create_variant(variant_name, kim)

        for rec in records:
            self.insert_student(rec, variant_id)
            for r in rec.get('result', []):
                self.insert_result(rec['id'], r)

        self.commit()
        return len(records)


def get_or_create_variant(cursor, name, kim):
    cursor.execute('SELECT id FROM variants WHERE name = ?', (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(
        'INSERT INTO variants (name, kim) VALUES (?, ?)',
        (name, kim)
    )
    vid = cursor.lastrowid
    logger.debug("Created variant id=%d name='%s'", vid, name)
    return vid
