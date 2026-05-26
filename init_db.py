import json
import os
import sqlite3
import re

from tqdm import tqdm

DB_PATH = os.path.join(os.getcwd(), 'ege_stat.db')
FILES_DIR = os.path.join(os.getcwd(), 'files')


def get_or_create_variant(cursor, name, kim):
    cursor.execute('SELECT id FROM variants WHERE name = ?', (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(
        'INSERT INTO variants (name, kim) VALUES (?, ?)',
        (name, kim)
    )
    return cursor.lastrowid


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kim INTEGER
        );

        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            user_id TEXT,
            variant_id INTEGER NOT NULL,
            primary_score INTEGER,
            secondary_score INTEGER,
            duration INTEGER,
            hide INTEGER,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (variant_id) REFERENCES variants(id)
        );

        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            key TEXT,
            score INTEGER,
            answer TEXT,
            number INTEGER,
            task_id INTEGER,
            FOREIGN KEY (student_id) REFERENCES students(id)
        );
    ''')

    conn.commit()
    return conn, cursor


def load_file(conn, cursor, filename):
    filepath = os.path.join(FILES_DIR, filename)
    variant_name = re.sub(r'\.json$', '', filename)

    with open(filepath, 'r', encoding='utf-8') as f:
        records = json.load(f)

    if not records:
        return 0

    kim = records[0].get('kim')
    variant_id = get_or_create_variant(cursor, variant_name, kim)

    count = 0
    for rec in records:
        cursor.execute('''
            INSERT OR REPLACE INTO students
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

        for r in rec.get('result', []):
            cursor.execute('''
                INSERT INTO results
                    (student_id, key, score, answer, number, task_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                rec['id'], r.get('key'), r.get('score'),
                r.get('answer'), r.get('number'), r.get('taskId')
            ))

        count += 1

    conn.commit()
    return count


def main():
    conn, cursor = init_db()

    json_files = sorted(
        f for f in os.listdir(FILES_DIR) if f.endswith('.json')
    )

    total = 0
    for filename in tqdm(json_files, desc="Загрузка в БД", unit="файл"):
        count = load_file(conn, cursor, filename)
        total += count

    conn.close()
    print(f'Загружено {total} студентов из {len(json_files)} вариантов.')


if __name__ == '__main__':
    main()
