import logging
import os
import re

import click
import pandas as pd
from tabulate import tabulate
from tqdm import tqdm

from database import Database, FILES_DIR

logger = logging.getLogger(__name__)


@click.group()
def cli():
    pass


@cli.command("show-results")
def show_results():
    db = Database()
    with db:
        students = db.get_students_pivot_data()

    if students.empty:
        click.echo("Нет данных.")
        return

    click.echo("\nФормат отображения:")
    click.echo("1) Первичные баллы")
    click.echo("2) Вторичные баллы")
    choice = input("> ").strip()

    value_col = 'secondary_score' if choice == '2' else 'primary_score'

    pivot = students.pivot_table(
        index='variant_name', columns='name', values=value_col,
        aggfunc='max'
    )
    pivot = pivot.astype('Int64').map(lambda x: int(x) if pd.notna(x) else '-')

    pivot.index.name = 'Тест'
    click.echo()
    click.echo(tabulate(pivot, headers='keys', tablefmt='grid'))


@cli.command("delete-test")
@click.argument("test_id", type=int)
def delete_test(test_id):
    db = Database()
    with db:
        variants = db.get_variants()

    if test_id not in variants['id'].values:
        click.echo("Тест с таким ID не найден.")
        return

    name = variants[variants['id'] == test_id].iloc[0]['name']
    click.confirm(f"Удалить тест «{name}» и все его результаты?", abort=True)

    with db:
        db.delete_variant(test_id)
        db.commit()
    click.echo(f"Тест «{name}» удалён.")


@cli.command("delete-student")
@click.argument("name")
def delete_student(name):
    click.confirm(f"Удалить ученика «{name}» и все его результаты?", abort=True)

    db = Database()
    with db:
        db.delete_student(name)
        db.commit()
    click.echo(f"Ученик «{name}» удалён.")


@cli.command("rename-student")
@click.argument("old_name")
@click.argument("new_name")
def rename_student(old_name, new_name):
    if old_name == new_name:
        click.echo("Имена совпадают.")
        return

    db = Database()
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
    click.echo(f"«{old_name}» переименован в «{new_name}».")


@cli.command("rename-test")
@click.argument("test_id", type=int)
@click.argument("new_name")
def rename_test(test_id, new_name):
    db = Database()
    with db:
        variants = db.get_variants()
        if test_id not in variants['id'].values:
            click.echo("Тест с таким ID не найден.")
            return
        old_name = variants[variants['id'] == test_id].iloc[0]['name']
        if new_name == old_name:
            click.echo("Названия совпадают.")
            return
        db.rename_variant(test_id, new_name)
        db.commit()
    click.echo(f"Тест «{old_name}» переименован в «{new_name}».")


@cli.command("load-files")
def load_new_files():
    db = Database()
    with db:
        existing = db.get_existing_variant_names()

    json_files = sorted(
        f for f in os.listdir(FILES_DIR) if f.endswith('.json')
    )
    new_files = [f for f in json_files if re.sub(r'\.json$', '', f) not in existing]

    if not new_files:
        click.echo("Новых файлов нет.")
        return

    total = 0
    for filename in tqdm(new_files, desc="Загрузка новых файлов", unit="файл"):
        variant_name = re.sub(r'\.json$', '', filename)
        with db:
            count = db.load_json_file(filename, variant_name)
        total += count

    click.echo(f"Загружено {len(new_files)} новых файлов.")


@cli.command("export-pdf")
@click.option("--score", type=click.Choice(['primary', 'secondary']), default='primary',
              help="Тип баллов")
def export_pdf(score):
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
        click.echo("Нет данных.")
        return

    value_col = 'secondary_score' if score == 'secondary' else 'primary_score'

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
    click.echo(f"PDF сохранён: {pdf_path}")


@cli.command("task-stats")
@click.option("--sort", type=click.Choice(['number', 'rate-asc', 'rate-desc']),
              default='number', help="Сортировка")
def task_stats(sort):
    db = Database()
    with db:
        stats = db.get_task_stats()

    if stats.empty:
        click.echo("Нет данных.")
        return

    stats = stats.astype({'task_number': int})

    if sort == 'rate-asc':
        stats = stats.sort_values('solve_rate', ascending=True)
    elif sort == 'rate-desc':
        stats = stats.sort_values('solve_rate', ascending=False)

    stats.columns = ['№ задания', '% решаемости']
    click.echo()
    click.echo("Статистика по номерам заданий (все ученики):")
    click.echo_via_pager(tabulate(stats, headers='keys', tablefmt='grid', showindex=False))


@cli.command("student-avg")
def student_avg():
    db = Database()
    with db:
        avg = db.get_student_avg()

    if avg.empty:
        click.echo("Нет данных.")
        return

    click.echo()
    click.echo("Средний балл учеников:")
    click.echo_via_pager(tabulate(avg, headers='keys', tablefmt='grid', showindex=False))


@cli.command("student-task-analysis")
@click.argument("name")
@click.option("--sort", type=click.Choice(['number', 'rate-asc', 'rate-desc']),
              default='number', help="Сортировка")
def student_task_analysis(name, sort):
    db = Database()
    with db:
        stats = db.get_student_task_analysis(name)

    if stats.empty:
        click.echo(f"У ученика «{name}» нет данных о заданиях.")
        return

    stats = stats.astype({'task_number': int})

    if sort == 'rate-asc':
        stats = stats.sort_values('solve_rate', ascending=True)
    elif sort == 'rate-desc':
        stats = stats.sort_values('solve_rate', ascending=False)

    click.echo(f"\nАнализ заданий для «{name}»:")
    stats.columns = ['№ задания', '% решаемости']
    click.echo_via_pager(tabulate(stats, headers='keys', tablefmt='grid', showindex=False))


# ---- Charts ----

@cli.group()
def chart():
    pass


@chart.command("task-stats")
def chart_task_stats():
    import matplotlib
    import matplotlib.pyplot as plt
    _setup_matplotlib(plt)

    db = Database()
    with db:
        stats = db.get_task_stats()

    if stats.empty:
        click.echo("Нет данных.")
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


@chart.command("student-avg")
@click.option("--score", type=click.Choice(['primary', 'secondary']), default='primary',
              help="Тип баллов")
def chart_student_avg(score):
    import matplotlib
    import matplotlib.pyplot as plt
    _setup_matplotlib(plt)

    col = 'avg_secondary' if score == 'secondary' else 'avg_primary'
    label = 'Вторичный' if score == 'secondary' else 'Первичный'

    db = Database()
    with db:
        avg = db.get_student_avg(col)

    if avg.empty:
        click.echo("Нет данных.")
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


@chart.command("student-task-analysis")
@click.argument("name")
def chart_student_task_analysis(name):
    import matplotlib
    import matplotlib.pyplot as plt
    _setup_matplotlib(plt)

    db = Database()
    with db:
        stats = db.get_student_task_analysis(name)

    if stats.empty:
        click.echo(f"У ученика «{name}» нет данных о заданиях.")
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


def _setup_matplotlib(plt):
    font_path = '/Library/Fonts/Arial Unicode.ttf'
    if os.path.exists(font_path):
        from matplotlib import font_manager
        font_manager.fontManager.addfont(font_path)
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams['axes.unicode_minus'] = False


def list_commands():
    click.echo()
    click.echo("=" * 40)
    click.echo("EgeStat — команды")
    click.echo("=" * 40)
    click.echo("")
    click.echo("Таблицы:")
    click.echo("  show-results              : результаты студентов по тестам")
    click.echo("  task-stats [--sort]       : статистика по заданиям")
    click.echo("  student-avg               : средний балл учеников")
    click.echo("  student-task-analysis NAME : анализ заданий ученика")
    click.echo("")
    click.echo("Управление:")
    click.echo("  delete-test TEST_ID       : удалить тест")
    click.echo("  delete-student NAME       : удалить ученика")
    click.echo("  rename-student OLD NEW    : переименовать ученика")
    click.echo("  rename-test ID NAME       : переименовать тест")
    click.echo("  load-files                : загрузить новые JSON")
    click.echo("  export-pdf [--score]      : экспорт в PDF")
    click.echo("")
    click.echo("Графики:")
    click.echo("  chart task-stats          : решаемость по заданиям")
    click.echo("  chart student-avg [--score]: средний балл учеников")
    click.echo("  chart student-task-analysis NAME : анализ заданий")
    click.echo("")
    click.echo("Справка:")
    click.echo("  <команда> --help")
    click.echo()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    cli()
