# Скилл: Работа с базой данных и миграции

Используй при изменении структуры БД (добавление таблиц, полей).

## Правила
- Если используешь SQLAlchemy, все модели наследуются от `Base` в `database.py`.
- Никогда не удаляй таблицу вручную, используй Alembic.

## Алгоритм (создание новой модели)
1. Создай файл в `src/models/` (например, `product.py`).
2. Опиши класс с `__tablename__`, колонками (`Column`, `Integer`, `String`).
3. Импортируй модель в `src/main.py` и в `alembic/env.py` (чтобы Alembic видел её).
4. Если проект на SQLite — просто запусти приложение (сработает `create_all`).
5. Если проект на PostgreSQL/Alembic:
   - Выполни `run_command("alembic revision --autogenerate -m 'add product'")`.
   - Проверь сгенерированный файл в `migrations/versions/`.
   - Выполни `run_command("alembic upgrade head")`.