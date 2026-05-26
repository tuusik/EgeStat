import os
import sqlite3
import pandas as pd
from tabulate import tabulate

DB_PATH = os.path.join(os.getcwd(), 'ege_stat.db')


def get_connection():
    return sqlite3.connect(DB_PATH)


def show_results():
    conn = get_connection()

    students = pd.read_sql_query('''
        SELECT s.name, v.name as variant_name,
               s.primary_score, s.secondary_score
        FROM students s
        JOIN variants v ON s.variant_id = v.id
    ''', conn)

    conn.close()

    if students.empty:
        print("Нет данных.")
        return

    print("\nФормат отображения:")
    print("1) Первичные баллы")
    print("2) Вторичные баллы")
    choice = input("> ").strip()

    value_col = 'secondary_score' if choice == '2' else 'primary_score'
    label = 'Вторичный балл' if choice == '2' else 'Первичный балл'

    pivot = students.pivot_table(
        index='name', columns='variant_name', values=value_col,
        aggfunc='max'
    )
    pivot = pivot.astype('Int64').map(lambda x: int(x) if pd.notna(x) else '-')

    pivot.index.name = 'Имя'
    print()
    print(tabulate(pivot, headers='keys', tablefmt='grid'))


def delete_test():
    conn = get_connection()
    variants = pd.read_sql_query(
        'SELECT id, name FROM variants ORDER BY name', conn
    )

    if variants.empty:
        conn.close()
        print("Нет тестов.")
        return

    print("\nВыберите тест для удаления:")
    for i, row in variants.iterrows():
        print(f"{i + 1}) {row['name']}")
    print("0) Отмена")

    choice = input("> ").strip()
    if not choice.isdigit():
        conn.close()
        return
    idx = int(choice)
    if idx == 0 or idx > len(variants):
        conn.close()
        return

    variant = variants.iloc[idx - 1]
    confirm = input(
        f"Удалить тест «{variant['name']}» и все его результаты? (д/н): "
    ).strip().lower()
    if confirm != 'д':
        conn.close()
        return

    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM results WHERE student_id IN '
        '(SELECT id FROM students WHERE variant_id = ?)',
        (int(variant['id']),)
    )
    cursor.execute('DELETE FROM students WHERE variant_id = ?', (int(variant['id']),))
    cursor.execute('DELETE FROM variants WHERE id = ?', (int(variant['id']),))
    conn.commit()
    conn.close()
    print(f"Тест «{variant['name']}» удалён.")


def rename_student():
    conn = get_connection()
    names = pd.read_sql_query(
        'SELECT DISTINCT name FROM students ORDER BY name', conn
    )
    conn.close()

    if names.empty:
        print("Нет учеников.")
        return

    print("\nВыберите ученика для переименования:")
    for i, row in names.iterrows():
        print(f"{i + 1}) {row['name']}")
    print("0) Отмена")

    choice = input("> ").strip()
    if not choice.isdigit():
        return
    idx = int(choice)
    if idx == 0 or idx > len(names):
        return

    old_name = names.iloc[idx - 1]['name']
    new_name = input(f"Новое имя для «{old_name}»: ").strip()
    if not new_name or new_name == old_name:
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM students WHERE name = ?', (new_name,))
    target_exists = cursor.fetchone()[0] > 0

    if target_exists:
        cursor.execute(
            'SELECT DISTINCT variant_id FROM students WHERE name = ?',
            (old_name,)
        )
        old_variants = {r[0] for r in cursor.fetchall()}

        cursor.execute(
            'SELECT variant_id FROM students WHERE name = ?',
            (new_name,)
        )
        new_variants = {r[0] for r in cursor.fetchall()}

        for vid in old_variants & new_variants:
            cursor.execute(
                'SELECT id, primary_score FROM students WHERE name = ? AND variant_id = ?',
                (old_name, vid)
            )
            old_rows = cursor.fetchall()

            cursor.execute(
                'SELECT id, primary_score FROM students WHERE name = ? AND variant_id = ?',
                (new_name, vid)
            )
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

    cursor.execute('UPDATE students SET name = ? WHERE name = ?', (new_name, old_name))
    conn.commit()
    conn.close()
    print(f"«{old_name}» переименован в «{new_name}».")


def rename_test():
    conn = get_connection()
    variants = pd.read_sql_query(
        'SELECT id, name FROM variants ORDER BY name', conn
    )

    if variants.empty:
        conn.close()
        print("Нет тестов.")
        return

    print("\nВыберите тест для переименования:")
    for i, row in variants.iterrows():
        print(f"{i + 1}) {row['name']}")
    print("0) Отмена")

    choice = input("> ").strip()
    if not choice.isdigit():
        conn.close()
        return
    idx = int(choice)
    if idx == 0 or idx > len(variants):
        conn.close()
        return

    variant = variants.iloc[idx - 1]
    new_name = input(f"Новое название для «{variant['name']}»: ").strip()
    if not new_name or new_name == variant['name']:
        conn.close()
        return

    cursor = conn.cursor()
    cursor.execute('UPDATE variants SET name = ? WHERE id = ?', (new_name, int(variant['id'])))
    conn.commit()
    conn.close()
    print(f"Тест «{variant['name']}» переименован в «{new_name}».")


def delete_student():
    conn = get_connection()
    names = pd.read_sql_query(
        'SELECT DISTINCT name FROM students ORDER BY name', conn
    )
    conn.close()

    if names.empty:
        print("Нет учеников.")
        return

    print("\nВыберите ученика для удаления:")
    for i, row in names.iterrows():
        print(f"{i + 1}) {row['name']}")
    print("0) Отмена")

    choice = input("> ").strip()
    if not choice.isdigit():
        return
    idx = int(choice)
    if idx == 0 or idx > len(names):
        return

    name = names.iloc[idx - 1]['name']
    confirm = input(
        f"Удалить ученика «{name}» и все его результаты? (д/н): "
    ).strip().lower()
    if confirm != 'д':
        return

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM results WHERE student_id IN '
        '(SELECT id FROM students WHERE name = ?)',
        (name,)
    )
    cursor.execute('DELETE FROM students WHERE name = ?', (name,))
    conn.commit()
    conn.close()
    print(f"Ученик «{name}» удалён.")


def main():
    while True:
        print()
        print("=" * 40)
        print("ГЛАВНОЕ МЕНЮ")
        print("=" * 40)
        print("1) Показать результаты за тесты")
        print("2) Удалить тест")
        print("3) Удалить ученика")
        print("4) Переименовать ученика")
        print("5) Переименовать тест")
        print("0) Выход")

        choice = input("> ").strip()

        if choice == '1':
            show_results()
        elif choice == '2':
            delete_test()
        elif choice == '3':
            delete_student()
        elif choice == '4':
            rename_student()
        elif choice == '5':
            rename_test()
        elif choice == '0':
            break
        else:
            print("Неверный выбор.")


if __name__ == '__main__':
    main()
