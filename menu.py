import os
import re

import pandas as pd
from tabulate import tabulate
from tqdm import tqdm

from database import Database, FILES_DIR


def show_results():
    db = Database()
    with db:
        students = db.get_students_pivot_data()

    if students.empty:
        print("Нет данных.")
        return

    print("\nФормат отображения:")
    print("1) Первичные баллы")
    print("2) Вторичные баллы")
    choice = input("> ").strip()

    value_col = 'secondary_score' if choice == '2' else 'primary_score'

    pivot = students.pivot_table(
        index='name', columns='variant_name', values=value_col,
        aggfunc='max'
    )
    pivot = pivot.astype('Int64').map(lambda x: int(x) if pd.notna(x) else '-')

    pivot.index.name = 'Имя'
    print()
    print(tabulate(pivot, headers='keys', tablefmt='grid'))


def delete_test():
    db = Database()
    with db:
        variants = db.get_variants()

    if variants.empty:
        print("Нет тестов.")
        return

    print("\nВыберите тест для удаления:")
    for i, row in variants.iterrows():
        print(f"{i + 1}) {row['name']}")
    print("0) Отмена")

    choice = input("> ").strip()
    if not choice.isdigit():
        return
    idx = int(choice)
    if idx == 0 or idx > len(variants):
        return

    variant = variants.iloc[idx - 1]
    confirm = input(
        f"Удалить тест «{variant['name']}» и все его результаты? (д/н): "
    ).strip().lower()
    if confirm != 'д':
        return

    with db:
        db.delete_variant(int(variant['id']))
        db.commit()
    print(f"Тест «{variant['name']}» удалён.")


def rename_student():
    db = Database()
    with db:
        names = db.get_student_names()

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

    with db:
        if db.target_name_exists(new_name):
            old_variants = db.get_student_variants(old_name)
            new_variants = db.get_student_variants(new_name)

            for vid in old_variants & new_variants:
                old_rows = db.get_student_scores_by_variant(old_name, vid)
                new_rows = db.get_student_scores_by_variant(new_name, vid)

                old_best = max(r[1] or 0 for r in old_rows)
                new_best = max(r[1] or 0 for r in new_rows)

                if old_best >= new_best:
                    loser_ids = [r[0] for r in new_rows]
                else:
                    loser_ids = [r[0] for r in old_rows]

                db.delete_student_by_ids(loser_ids)

        db.rename_student_simple(old_name, new_name)
        db.commit()
    print(f"«{old_name}» переименован в «{new_name}».")


def rename_test():
    db = Database()
    with db:
        variants = db.get_variants()

    if variants.empty:
        print("Нет тестов.")
        return

    print("\nВыберите тест для переименования:")
    for i, row in variants.iterrows():
        print(f"{i + 1}) {row['name']}")
    print("0) Отмена")

    choice = input("> ").strip()
    if not choice.isdigit():
        return
    idx = int(choice)
    if idx == 0 or idx > len(variants):
        return

    variant = variants.iloc[idx - 1]
    new_name = input(f"Новое название для «{variant['name']}»: ").strip()
    if not new_name or new_name == variant['name']:
        return

    with db:
        db.rename_variant(int(variant['id']), new_name)
        db.commit()
    print(f"Тест «{variant['name']}» переименован в «{new_name}».")


def delete_student():
    db = Database()
    with db:
        names = db.get_student_names()

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

    with db:
        db.delete_student(name)
        db.commit()
    print(f"Ученик «{name}» удалён.")


def load_new_files():
    db = Database()
    with db:
        existing = db.get_existing_variant_names()

    json_files = sorted(
        f for f in os.listdir(FILES_DIR) if f.endswith('.json')
    )
    new_files = [f for f in json_files if re.sub(r'\.json$', '', f) not in existing]

    if not new_files:
        print("Новых файлов нет.")
        return

    total = 0
    for filename in tqdm(new_files, desc="Загрузка новых файлов", unit="файл"):
        variant_name = re.sub(r'\.json$', '', filename)
        with db:
            count = db.load_json_file(filename, variant_name)
        total += count

    print(f"Загружено {len(new_files)} новых файлов.")


def export_pdf():
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import getSampleStyleSheet

    db = Database()
    with db:
        students = db.get_students_pivot_data()

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

    n_cols = len(pivot.columns) + 1
    data = [['Имя'] + [str(i) for i in range(1, n_cols)]]
    for name, row in pivot.iterrows():
        data.append([name, *[str(v) for v in row.values]])

    name_width = max(30, min(55, max(len(n) for n in pivot.index) * 0.65 + 6)) * mm
    data_col_width = 8 * mm

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


def task_stats():
    db = Database()
    with db:
        stats = db.get_task_stats()

    if stats.empty:
        print("Нет данных.")
        return

    stats = stats.astype({'task_number': int})

    print("\nСортировать по:")
    print("1) Номеру задания")
    print("2) % решаемости (от худших к лучшим)")
    print("3) % решаемости (от лучших к худшим)")
    choice = input("> ").strip()

    if choice == '2':
        stats = stats.sort_values('solve_rate', ascending=True)
    elif choice == '3':
        stats = stats.sort_values('solve_rate', ascending=False)

    stats.columns = ['№ задания', '% решаемости']
    print()
    print("Статистика по номерам заданий (все ученики):")
    print(tabulate(stats, headers='keys', tablefmt='grid', showindex=False))


def student_avg():
    db = Database()
    with db:
        avg = db.get_student_avg()

    if avg.empty:
        print("Нет данных.")
        return

    print()
    print("Средний балл учеников:")
    avg.columns = ['Имя', 'Ср. первичный', 'Ср. вторичный', 'Тестов']
    print(tabulate(avg, headers='keys', tablefmt='grid', showindex=False))


def student_task_analysis():
    db = Database()
    with db:
        names = db.get_student_names()

    if names.empty:
        print("Нет учеников.")
        return

    print("\nВыберите ученика:")
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

    with db:
        stats = db.get_student_task_analysis(name)

    if stats.empty:
        print(f"У ученика «{name}» нет данных о заданиях.")
        return

    stats = stats.astype({'task_number': int})

    print("\nСортировать по:")
    print("1) Номеру задания")
    print("2) % решаемости (от худших к лучшим)")
    print("3) % решаемости (от лучших к худшим)")
    choice = input("> ").strip()

    if choice == '2':
        stats = stats.sort_values('solve_rate', ascending=True)
    elif choice == '3':
        stats = stats.sort_values('solve_rate', ascending=False)

    print(f"\nАнализ заданий для «{name}»:")
    stats.columns = ['№ задания', '% решаемости']
    print(tabulate(stats, headers='keys', tablefmt='grid', showindex=False))


def show_charts():
    import matplotlib
    import matplotlib.pyplot as plt

    font_path = '/Library/Fonts/Arial Unicode.ttf'
    if os.path.exists(font_path):
        from matplotlib import font_manager
        font_manager.fontManager.addfont(font_path)
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams['axes.unicode_minus'] = False

    while True:
        print()
        print("--- ГРАФИКИ ---")
        print("1) Решаемость по заданиям (все ученики)")
        print("2) Средний балл учеников")
        print("3) Анализ заданий конкретного ученика")
        print("0) Назад")
        choice = input("> ").strip()

        if choice == '0':
            plt.close('all')
            return
        elif choice == '1':
            _chart_task_stats(plt)
        elif choice == '2':
            _chart_student_avg(plt)
        elif choice == '3':
            _chart_student_task_analysis(plt)
        else:
            print("Неверный выбор.")


def _chart_task_stats(plt):
    db = Database()
    with db:
        stats = db.get_task_stats()

    if stats.empty:
        print("Нет данных.")
        return

    stats = stats.astype({'task_number': int})

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(stats['task_number'], stats['solve_rate'], color='#4472C4', edgecolor='white')
    ax.set_xlabel('Номер задания')
    ax.set_ylabel('% решаемости')
    ax.set_title('Решаемость заданий (все ученики)')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0f}%'))
    ax.set_xticks(stats['task_number'])
    ax.set_ylim(0, 105)

    for bar, rate in zip(bars, stats['solve_rate']):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f'{rate:.0f}%', ha='center', va='bottom', fontsize=8)

    fig.tight_layout()
    plt.show()
    plt.close(fig)


def _chart_student_avg(plt):
    print("\nБаллы:")
    print("1) Первичные")
    print("2) Вторичные")
    score_choice = input("> ").strip()
    col = 'avg_secondary' if score_choice == '2' else 'avg_primary'
    label = 'Вторичный' if score_choice == '2' else 'Первичный'

    db = Database()
    with db:
        avg = db.get_student_avg(col)

    if avg.empty:
        print("Нет данных.")
        return

    fig, ax = plt.subplots(figsize=(10, max(4, len(avg) * 0.4)))
    colors = ['#4472C4', '#ED7D31', '#70AD47', '#FFC000', '#5B9BD5', '#A5A5A5']
    bar_colors = [colors[i % len(colors)] for i in range(len(avg))]
    bars = ax.barh(avg['name'], avg[col], color=bar_colors, edgecolor='white')
    ax.set_xlabel(f'Средний {label.lower()} балл')
    ax.set_title(f'Средний {label.lower()} балл учеников')
    ax.invert_yaxis()

    for bar, val in zip(bars, avg[col]):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f'{val:.1f}', ha='left', va='center', fontsize=9)

    fig.tight_layout()
    plt.show()
    plt.close(fig)


def _chart_student_task_analysis(plt):
    db = Database()
    with db:
        names = db.get_student_names()

    if names.empty:
        print("Нет учеников.")
        return

    print("\nВыберите ученика:")
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

    with db:
        stats = db.get_student_task_analysis(name)

    if stats.empty:
        print(f"У ученика «{name}» нет данных о заданиях.")
        return

    stats = stats.astype({'task_number': int})

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(stats['task_number'], stats['solve_rate'], color='#70AD47', edgecolor='white')
    ax.set_xlabel('Номер задания')
    ax.set_ylabel('% решаемости')
    ax.set_title(f'Решаемость заданий — {name}')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0f}%'))
    ax.set_xticks(stats['task_number'])
    ax.set_ylim(0, 105)

    for bar, rate in zip(bars, stats['solve_rate']):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f'{rate:.0f}%', ha='center', va='bottom', fontsize=8)

    fig.tight_layout()
    plt.show()
    plt.close(fig)


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
        print("--- Аналитика ---")
        print("8) Статистика по заданиям")
        print("9) Средний балл учеников")
        print("10) Анализ заданий ученика")
        print("--- Графики ---")
        print("11) Построить графики")
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
        elif choice == '8':
            task_stats()
        elif choice == '9':
            student_avg()
        elif choice == '10':
            student_task_analysis()
        elif choice == '11':
            show_charts()
        elif choice == '0':
            break
        else:
            print("Неверный выбор.")


if __name__ == '__main__':
    main()
