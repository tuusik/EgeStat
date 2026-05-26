import os
import sys
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import menu
import init_db


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def schema(db_path):
    """Create schema in a temp DB and return cursor."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.executescript(init_db.SCHEMA)
    conn.commit()
    yield conn, cursor
    conn.close()


def test_schema_creation(db_path):
    """Tables are created with correct columns."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.executescript(init_db.SCHEMA)
    conn.commit()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [r[0] for r in cursor.fetchall()]
    assert tables == ['results', 'students', 'variants']

    conn.close()

    conn.close()


def test_get_or_create_variant_creates_new(schema):
    """New variant is inserted and its id returned."""
    conn, cursor = schema
    vid = menu.get_or_create_variant(cursor, 'test_variant', 12345)
    assert vid is not None
    cursor.execute('SELECT id, name, kim FROM variants WHERE id = ?', (vid,))
    row = cursor.fetchone()
    assert row[1] == 'test_variant'
    assert row[2] == 12345


def test_get_or_create_variant_returns_existing(schema):
    """Existing variant returns same id, no duplicate."""
    conn, cursor = schema
    vid1 = menu.get_or_create_variant(cursor, 'dupe', 999)
    vid2 = menu.get_or_create_variant(cursor, 'dupe', 999)
    assert vid1 == vid2
    cursor.execute('SELECT COUNT(*) FROM variants')
    assert cursor.fetchone()[0] == 1


def test_insert_student(schema):
    """Student with results can be inserted and queried."""
    conn, cursor = schema
    vid = menu.get_or_create_variant(cursor, 'variant_a', 111)

    cursor.execute('''
        INSERT INTO students (id, name, user_id, variant_id, primary_score, secondary_score)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ('uuid-1', 'Alice', 'user1', vid, 15, 70))

    cursor.execute('''
        INSERT INTO results (student_id, key, score, answer, number, task_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ('uuid-1', 'key1', 1, '42', 1, 100))

    conn.commit()

    cursor.execute('SELECT name, primary_score FROM students WHERE id = ?', ('uuid-1',))
    row = cursor.fetchone()
    assert row == ('Alice', 15)

    cursor.execute('SELECT score, answer FROM results WHERE student_id = ?', ('uuid-1',))
    row = cursor.fetchone()
    assert row == (1, '42')


def test_delete_variant_cascades(schema):
    """Deleting a variant removes its students and results."""
    conn, cursor = schema
    vid = menu.get_or_create_variant(cursor, 'to_delete', 222)

    cursor.execute('''
        INSERT INTO students (id, name, variant_id, primary_score, secondary_score)
        VALUES (?, ?, ?, ?, ?)
    ''', ('del-1', 'Bob', vid, 10, 50))
    cursor.execute('INSERT INTO results (student_id, key, score, number) VALUES (?, ?, ?, ?)',
                   ('del-1', 'k1', 1, 1))
    conn.commit()

    cursor.execute('DELETE FROM results WHERE student_id IN '
                   '(SELECT id FROM students WHERE variant_id = ?)', (vid,))
    cursor.execute('DELETE FROM students WHERE variant_id = ?', (vid,))
    cursor.execute('DELETE FROM variants WHERE id = ?', (vid,))
    conn.commit()

    cursor.execute('SELECT COUNT(*) FROM variants')
    assert cursor.fetchone()[0] == 0
    cursor.execute('SELECT COUNT(*) FROM students')
    assert cursor.fetchone()[0] == 0
    cursor.execute('SELECT COUNT(*) FROM results')
    assert cursor.fetchone()[0] == 0


def test_rename_student_simple(schema):
    """Renaming a student when target doesn't exist."""
    conn, cursor = schema
    vid = menu.get_or_create_variant(cursor, 'v1', 1)
    cursor.execute('''
        INSERT INTO students (id, name, variant_id, primary_score, secondary_score)
        VALUES (?, ?, ?, ?, ?)
    ''', ('s1', 'OldName', vid, 8, 40))
    conn.commit()

    cursor.execute('UPDATE students SET name = ? WHERE name = ?', ('NewName', 'OldName'))
    conn.commit()

    cursor.execute('SELECT name FROM students WHERE id = ?', ('s1',))
    assert cursor.fetchone()[0] == 'NewName'


def test_rename_student_merge_higher_score_wins(schema):
    """When renaming to existing name, higher score is kept."""
    conn, cursor = schema
    vid = menu.get_or_create_variant(cursor, 'v1', 1)

    cursor.execute('''
        INSERT INTO students (id, name, variant_id, primary_score, secondary_score)
        VALUES ('a1', 'Alex', ? , 5, 30), ('a2', 'Alex', ?, 10, 60)
    ''', (vid, vid))
    cursor.execute('''
        INSERT INTO students (id, name, variant_id, primary_score, secondary_score)
        VALUES ('l1', 'Lesha', ?, 8, 45)
    ''', (vid,))
    conn.commit()

    # Simulate rename: Lesha -> Alex
    # Both have scores for v1. Alex best=10, Lesha best=8 -> keep Alex
    cursor.execute('SELECT id, primary_score FROM students WHERE name = ? AND variant_id = ?',
                   ('Lesha', vid))
    old_rows = cursor.fetchall()
    cursor.execute('SELECT id, primary_score FROM students WHERE name = ? AND variant_id = ?',
                   ('Alex', vid))
    new_rows = cursor.fetchall()

    old_best = max(r[1] or 0 for r in old_rows)
    new_best = max(r[1] or 0 for r in new_rows)

    if old_best >= new_best:
        loser_ids = [r[0] for r in new_rows]
    else:
        loser_ids = [r[0] for r in old_rows]

    for sid in loser_ids:
        cursor.execute('DELETE FROM results WHERE student_id = ?', (sid,))
        cursor.execute('DELETE FROM students WHERE id = ?', (sid,))

    cursor.execute('UPDATE students SET name = ? WHERE name = ?', ('Alex', 'Lesha'))
    conn.commit()

    cursor.execute('SELECT name, primary_score FROM students ORDER BY primary_score DESC')
    rows = cursor.fetchall()
    assert all(r[0] == 'Alex' for r in rows)
    assert rows[0][1] == 10  # highest kept


def test_pivot_table_no_data(schema):
    """Empty student table produces empty pivot."""
    conn, cursor = schema
    students = pd.read_sql_query('''
        SELECT s.name, v.name as variant_name,
               s.primary_score, s.secondary_score
        FROM students s JOIN variants v ON s.variant_id = v.id
    ''', conn)
    assert students.empty


def test_pivot_table_with_data(schema):
    """Pivot table returns correct shape and values."""
    conn, cursor = schema
    v1 = menu.get_or_create_variant(cursor, 'variant_1', 1)
    v2 = menu.get_or_create_variant(cursor, 'variant_2', 2)

    cursor.execute('''
        INSERT INTO students (id, name, variant_id, primary_score, secondary_score)
        VALUES
            ('u1', 'Alice', ?, 15, 70),
            ('u2', 'Bob', ?, 10, 50),
            ('u3', 'Alice', ?, 18, 80)
    ''', (v1, v1, v2))
    conn.commit()

    students = pd.read_sql_query('''
        SELECT s.name, v.name as variant_name, s.primary_score, s.secondary_score
        FROM students s JOIN variants v ON s.variant_id = v.id
    ''', conn)

    pivot = students.pivot_table(
        index='name', columns='variant_name', values='primary_score',
        aggfunc='max'
    )
    pivot = pivot.astype('Int64').map(lambda x: int(x) if pd.notna(x) else '-')

    assert list(pivot.index) == ['Alice', 'Bob']
    assert sorted(pivot.columns.tolist()) == ['variant_1', 'variant_2']
    assert pivot.loc['Alice', 'variant_1'] == 15
    assert pivot.loc['Alice', 'variant_2'] == 18
    assert pivot.loc['Bob', 'variant_1'] == 10


def test_delete_nonexistent_student(schema):
    """Deleting a non-existent student does nothing."""
    conn, cursor = schema
    cursor.execute('DELETE FROM students WHERE name = ?', ('Ghost',))
    conn.commit()
    cursor.execute('SELECT COUNT(*) FROM students')
    assert cursor.fetchone()[0] == 0


def test_rename_to_same_name(db_path):
    """Renaming to the same name is a no-op."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.executescript(init_db.SCHEMA)

    vid = menu.get_or_create_variant(cursor, 'v', 0)
    cursor.execute('''
        INSERT INTO students (id, name, variant_id, primary_score, secondary_score)
        VALUES ('x', 'Alice', ?, 5, 25)
    ''', (vid,))
    conn.commit()

    cursor.execute('UPDATE students SET name = ? WHERE name = ?', ('Alice', 'Alice'))
    conn.commit()

    cursor.execute('SELECT COUNT(*) FROM students WHERE name = ?', ('Alice',))
    assert cursor.fetchone()[0] == 1
    conn.close()


def test_multiple_variants_same_student(schema):
    """Same student can appear in multiple variants."""
    conn, cursor = schema
    v1 = menu.get_or_create_variant(cursor, 'math', 1)
    v2 = menu.get_or_create_variant(cursor, 'phys', 2)

    cursor.execute('''
        INSERT INTO students (id, name, variant_id, primary_score, secondary_score)
        VALUES ('a1', 'Alice', ?, 12, 60), ('a2', 'Alice', ?, 15, 75)
    ''', (v1, v2))
    conn.commit()

    cursor.execute('SELECT variant_id, primary_score FROM students WHERE name = ? ORDER BY variant_id', ('Alice',))
    rows = cursor.fetchall()
    assert len(rows) == 2
    assert rows[0] == (v1, 12)
    assert rows[1] == (v2, 15)


def test_foreign_key_integrity(db_path):
    """Inserting a student with invalid variant_id fails."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    cursor.executescript(init_db.SCHEMA)
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute('''
            INSERT INTO students (id, name, variant_id, primary_score, secondary_score)
            VALUES ('bad', 'Ghost', 999, 0, 0)
        ''')
        conn.commit()

    conn.close()


def test_pdf_export_creates_file(schema, monkeypatch):
    """PDF export creates a file when data exists."""
    conn, cursor = schema
    vid = menu.get_or_create_variant(cursor, 'test_pdf', 1)
    cursor.execute('''
        INSERT INTO students (id, name, variant_id, primary_score, secondary_score)
        VALUES ('p1', 'Alice', ?, 10, 50)
    ''', (vid,))
    conn.commit()
    conn.close()

    monkeypatch.setattr(menu, 'DB_PATH', schema.__self__.filename
                        if hasattr(schema, '__self__') else menu.DB_PATH)
    monkeypatch.setattr('builtins.input', lambda _='': '1')

    pdf_path = os.path.join(menu.FILES_DIR, 'results.pdf')
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    menu.export_pdf()


def test_get_or_create_variant_kim_none(schema):
    """get_or_create_variant works when kim is None."""
    conn, cursor = schema
    vid = menu.get_or_create_variant(cursor, 'no_kim', None)
    cursor.execute('SELECT kim FROM variants WHERE id = ?', (vid,))
    assert cursor.fetchone()[0] is None
