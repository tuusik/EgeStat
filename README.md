# EgeStat

Парсер результатов ЕГЭ-статистики с сайта kompege.ru и работа с ними через терминальное меню.

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

### 1. Парсинг данных с kompege.ru

```bash
source EgeStat_environment/bin/activate
python3 parse_kompege.py
```

JSON-файлы сохраняются в папку `files/`.

### 2. Первичная загрузка в БД

```bash
source EgeStat_environment/bin/activate
python3 init_db.py
```

Создаёт `ege_stat.db` с таблицами `variants`, `students`, `results`.
При повторном запуске данные не перезаписываются.

### 3. Меню

```bash
source EgeStat_environment/bin/activate
python3 menu.py
```

| № | Действие |
|---|----------|
| 1 | Показать результаты — сводная таблица (студенты × тесты), баллы или проценты |
| 2 | Удалить тест |
| 3 | Удалить ученика |
| 4 | Переименовать ученика (с мержем результатов) |
| 5 | Переименовать тест |
| 6 | Загрузить новые файлы из `files/` (без перезаписи) |
| 7 | Экспорт в PDF — `files/results.pdf` |
| **Аналитика** | |
| 8 | Статистика по заданиям — % решаемости по номерам (с сортировкой) |
| 9 | Средний балл учеников |
| 10 | Анализ заданий ученика — его % решаемости по номерам (с сортировкой) |

### 4. Добавление новых данных

Если появились новые JSON-файлы в `files/` — запусти пункт **6** в меню.
Скрипт найдёт только новые варианты и загрузит их, не трогая существующие.

## Тесты

```bash
source EgeStat_environment/bin/activate
pytest -v
```

19 тестов: схема БД, CRUD, pivot table, rename с мержем, аналитика, PDF.

## Структура БД

- **variants** — варианты тестов (id, name, kim)
- **students** — ученики (id, name, баллы, variant_id)
- **results** — ответы на задания (student_id, key, score, number, task_id)
