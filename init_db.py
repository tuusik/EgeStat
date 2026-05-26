import logging
import os
import re
import sqlite3

from tqdm import tqdm

from database import Database, DB_PATH, FILES_DIR

logger = logging.getLogger(__name__)

SCHEMA: str = '''
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
'''


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript(SCHEMA)
    conn.commit()
    conn.close()


def main() -> None:
    init_db()

    db = Database()
    with db:
        existing = db.get_existing_variant_names()
        if existing:
            print("База уже содержит данные. Используй пункт меню «Загрузить новые файлы».")
            return

    json_files: list[str] = sorted(
        f for f in os.listdir(FILES_DIR) if f.endswith('.json')
    )

    total: int = 0
    for filename in tqdm(json_files, desc="Загрузка в БД", unit="файл"):
        db = Database()
        with db:
            count: int = db.load_json_file(filename, re.sub(r'\.json$', '', filename))
        total += count

    print(f'Загружено {total} студентов из {len(json_files)} вариантов.')


if __name__ == '__main__':
    main()
