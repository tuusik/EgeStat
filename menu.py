import json
import os
import re
import sqlite3
import pandas as pd
from tabulate import tabulate
from tqdm import tqdm

DB_PATH = os.path.join(os.getcwd(), 'ege_stat.db')
FILES_DIR = os.path.join(os.getcwd(), 'files')


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


def load_new_files():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT name FROM variants')
    existing = {r[0] for r in cursor.fetchall()}

    json_files = sorted(
        f for f in os.listdir(FILES_DIR) if f.endswith('.json')
    )
    new_files = [f for f in json_files if re.sub(r'\.json$', '', f) not in existing]

    if not new_files:
        print("Новых файлов нет.")
        conn.close()
        return

    for filename in tqdm(new_files, desc="Загрузка новых файлов", unit="файл"):
        filepath = os.path.join(FILES_DIR, filename)
        variant_name = re.sub(r'\.json$', '', filename)

        with open(filepath, 'r', encoding='utf-8') as f:
            records = json.load(f)

        if not records:
            continue

        kim = records[0].get('kim')
        variant_id = get_or_create_variant(cursor, variant_name, kim)

        for rec in records:
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

            for r in rec.get('result', []):
                cursor.execute('''
                    INSERT INTO results
                        (student_id, key, score, answer, number, task_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    rec['id'], r.get('key'), r.get('score'),
                    r.get('answer'), r.get('number'), r.get('taskId')
                ))

        conn.commit()

    conn.close()
    print(f"Загружено {len(new_files)} новых файлов.")


def export_pdf():
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import getSampleStyleSheet

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

    print("\nФормат экспорта:")
    print("1) Первичные баллы")
    print("2) Вторичные баллы")
    choice = input("> ").strip()

    value_col = 'secondary_score' if choice == '2' else 'primary_score'

    pivot = students.pivot_table(
        index='name', columns='variant_name', values=value_col,
        aggfunc='max'
    )
    pivot = pivot.astype('Int64').map(lambda x: int(x) if pd.notna(x) else '-')

    font_path = '/Library/Fonts/Arial Unicode.ttf'
    pdfmetrics.registerFont(TTFont('ArialUnicode', font_path))

    styles = getSampleStyleSheet()
    style_normal = styles['Normal']
    style_normal.fontName = 'ArialUnicode'

    # Build table data — headers are just numbers
    n_cols = len(pivot.columns) + 1
    data = [['Имя'] + [str(i) for i in range(1, n_cols)]]
    for name, row in pivot.iterrows():
        data.append([name, *[str(v) for v in row.values]])

    # Column widths
    name_width = max(30, min(55, max(len(n) for n in pivot.index) * 0.65 + 6)) * mm
    data_col_width = 8 * mm  # fixed narrow width for numbers

    col_widths = [name_width] + [data_col_width] * (n_cols - 1)
    page_width = landscape(A4)[0] - 20 * mm
    if sum(col_widths) > page_width:
        data_col_width = (page_width - name_width) / (n_cols - 1)
        col_widths = [name_width] + [data_col_width] * (n_cols - 1)

    pdf_path = os.path.join(FILES_DIR, 'results.pdf')
    doc = SimpleDocTemplate(
        pdf_path, pagesize=landscape(A4),
        leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=10 * mm, bottomMargin=10 * mm
    )

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'ArialUnicode'),
        ('FONTSIZE', (0, 0), (-1, -1), 6),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#D9E2F3')]),
    ]))

    elems = [Paragraph("Результаты тестов", style_normal), Spacer(1, 5 * mm), table]
    doc.build(elems)
    print(f"PDF сохранён: {pdf_path}")


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
        print("6) Загрузить новые файлы")
        print("7) Экспорт в PDF")
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
        elif choice == '6':
            load_new_files()
        elif choice == '7':
            export_pdf()
        elif choice == '0':
            break
        else:
            print("Неверный выбор.")


if __name__ == '__main__':
    main()
