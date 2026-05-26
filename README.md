# EgeStat

Парсер результатов ЕГЭ-статистики с сайта kompege.ru и работа с ними через терминальное меню.

## Установка

```bash
git clone https://github.com/tuusik/EgeStat.git
cd EgeStat

python3 -m venv EgeStat_environment
source EgeStat_environment/bin/activate      # macOS / Linux
# или .\EgeStat_environment\Scripts\activate  # Windows

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

Доступные пункты:

| № | Действие |
|---|----------|
| 1 | Показать результаты — сводная таблица (студенты × тесты), баллы или проценты |
| 2 | Удалить тест |
| 3 | Удалить ученика |
| 4 | Переименовать ученика (с мержем результатов) |
| 5 | Переименовать тест |
| 6 | Загрузить новые файлы из `files/` (без перезаписи существующих) |
| 7 | Экспорт в PDF — `files/results.pdf` |

### 4. Добавление новых данных

Если появились новые JSON-файлы в `files/` — запусти пункт **6** в меню.
Скрипт найдёт только новые варианты и загрузит их без удаления старых.

## Тесты

```bash
source EgeStat_environment/bin/activate
pytest -v
```

## Структура БД

- **variants** — варианты тестов (id, name, kim)
- **students** — ученики (id, name, баллы, variant_id)
- **results** — ответы на задания (student_id, key, score, task_id)
