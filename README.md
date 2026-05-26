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

### 3. Меню

```bash
python3 menu.py
```

```
========================================
           ГЛАВНОЕ МЕНЮ
========================================
1) Показать результаты за тесты
2) Удалить тест
3) Удалить ученика
4) Переименовать ученика
5) Переименовать тест
6) Загрузить новые файлы
7) Экспорт в PDF
--- Аналитика ---
8) Статистика по заданиям
9) Средний балл учеников
10) Анализ заданий ученика
--- Графики ---
11) Построить графики
0) Выход
```

### 4. Добавление новых данных

Новые JSON положи в `files/` → выбери **6** в меню — скрипт загрузит только новые варианты.

---
0) Назад
```

**1 — Решаемость по заданиям** — столбчатая диаграмма % решаемости по каждому номеру.

![Task Stats](https://raw.githubusercontent.com/tuusik/EgeStat/main/screenshots/chart_task_stats.png)

**2 — Средний балл учеников** — горизонтальная диаграмма, с выбором первичных/вторичных баллов.

![Student Avg](https://raw.githubusercontent.com/tuusik/EgeStat/main/screenshots/chart_student_avg.png)

**3 — Анализ заданий ученика** — столбчатая диаграмма для выбранного ученика.

![Student Tasks](https://raw.githubusercontent.com/tuusik/EgeStat/main/screenshots/chart_student_tasks.png)


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
