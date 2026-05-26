# EgeStat

Парсер и анализ результатов ЕГЭ с [kompege.ru](https://kompege.ru) через терминальное меню.

## Установка

```bash
git clone https://github.com/tuusik/EgeStat.git
cd EgeStat

python3 -m venv EgeStat_environment
source EgeStat_environment/bin/activate      # macOS / Linux
# .\EgeStat_environment\Scripts\activate     # Windows

pip install -r requirements.txt
```

## Использование

### 1. Парсинг

Скачивает JSON с результатами учеников с kompege.ru:

```bash
python3 parse_kompege.py
```

Файлы сохраняются в `files/`.

### 2. Инициализация БД

```bash
python3 init_db.py
```

Создаёт `ege_stat.db`. При повторном запуске данные не перезаписываются.

### 3. CLI

```bash
python3 menu.py --help
```

```
Usage: menu.py [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  show-results                 результаты студентов по тестам
  task-stats                   статистика по заданиям (--sort)
  student-avg                  средний балл учеников
  student-task-analysis NAME   анализ заданий ученика
  delete-test TEST_ID          удалить тест
  delete-student NAME          удалить ученика
  rename-student OLD NEW       переименовать ученика
  rename-test ID NAME          переименовать тест
  load-files                   загрузить новые JSON
  export-pdf                   экспорт в PDF (--score)
  chart task-stats             график решаемости по заданиям
  chart student-avg            график среднего балла (--score)
  chart student-task-analysis NAME   график анализа заданий
```

Каждая команда принимает `--help`:

```bash
python3 menu.py task-stats --help
python3 menu.py chart student-avg --help
```

### 4. Добавление новых данных

Новые JSON положи в `files/` → запусти:

```bash
python3 menu.py load-files
```

---

## Примеры работы

### 📊 Сводная таблица

```bash
python3 menu.py show-results
```

Студенты × тесты, первичные или вторичные баллы:

```
+--------+-------------+-------------+-------------+
| Имя    | Вариант 1   | Вариант 2   | Вариант 3   |
+========+=============+=============+=============+
| Иванов | 15          | -           | 18          |
+--------+-------------+-------------+-------------+
| Петров | 12          | 14          | -           |
+--------+-------------+-------------+-------------+
| Сидоров | -          | 10          | 16          |
+--------+-------------+-------------+-------------+
```

### 📈 Статистика по заданиям

```bash
python3 menu.py task-stats --sort rate-asc
```

```
Статистика по номерам заданий (все ученики):
+--------------+----------------+
| № задания    | % решаемости   |
+==============+================+
| 27           | 12.5           |
| 26           | 25.0           |
| 24           | 37.5           |
| 23           | 62.5           |
| 1            | 87.5           |
| 2            | 100.0          |
+--------------+----------------+
```

### 📉 Средний балл учеников

```bash
python3 menu.py student-avg
```

### 🔍 Анализ заданий ученика

```bash
python3 menu.py student-task-analysis Иванов --sort number
```

```
Анализ заданий для «Иванов»:
+--------------+----------------+
| № задания    | % решаемости   |
+==============+================+
| 1            | 100.0          |
| 2            | 100.0          |
| 3            | 50.0           |
| 4            | 0.0            |
+--------------+----------------+
```

### 📄 PDF-экспорт

```bash
python3 menu.py export-pdf --score primary
```

Создаёт `files/results.pdf` — сводная таблица в landscape A4, столбцы пронумерованы.

### Управление данными

```bash
python3 menu.py delete-test 1          # удалить тест с ID=1
python3 menu.py delete-student Иванов  # удалить ученика
python3 menu.py rename-student Иван Иван2   # переименовать с мержем
python3 menu.py rename-test 1 "Вариант А"   # переименовать тест
```

### 📊 Графики

```bash
python3 menu.py chart task-stats
python3 menu.py chart student-avg --score secondary
python3 menu.py chart student-task-analysis Иванов
```

Каждый график открывается в отдельном окне.

**Решаемость по заданиям:**

![Решаемость по заданиям](screenshots/chart_task_stats.png)

**Средний балл учеников:**

![Средний балл учеников](screenshots/chart_student_avg.png)

**Анализ заданий ученика:**

![Анализ заданий ученика](screenshots/chart_student_tasks.png)

---

## Тесты

```bash
pytest -v
```

21 тест: схема БД, CRUD, pivot table, rename с мержем, аналитика, PDF, графики.

## Структура БД

- **variants** — варианты тестов (id, name, kim)
- **students** — ученики (id, name, баллы, variant_id)
- **results** — ответы на задания (student_id, key, score, number, task_id)
