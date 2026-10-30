"""Входная точка: интерактивный чат с агентом в терминале."""

import argparse
import json
import os
import sys
from pathlib import Path

# Добавляем путь к агенту, чтобы импорты работали, даже если мы запускаем
# скрипт из другой директории (например, из папки нового проекта).
sys.path.insert(0, str(Path(__file__).parent))

from agent.core import Agent
from memory.tokenizer import count_tokens


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Agent for coding")
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory where the agent will work (default: current dir)",
    )
    args = parser.parse_args()

    # ── 1. Смена рабочей директории ───────────────────────────────
    project_dir = args.project_dir.resolve()
    if not project_dir.exists():
        print(f"⚠️ Directory {project_dir} does not exist. Creating it...")
        project_dir.mkdir(parents=True)
    
    os.chdir(project_dir)
    print(f"📂 Рабочая директория: {project_dir}")
    print("🤖 Агент запущен. Команды: /reset — сбросить историю, /exit — выход.\n")

    # История теперь хранится ВНУТРИ проекта, а не в my_agent
    history_file = project_dir / "chat_history.json"

    # ── 2. Загрузка истории ───────────────────────────────────────
    if history_file.exists():
        try:
            agent = Agent.load(history_file)
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"⚠️ Не удалось загрузить историю ({exc}). Начинаем заново.")
            agent = Agent()
    else:
        agent = Agent()

    # ── 3. Основной цикл ──────────────────────────────────────────
    try:
        while True:
            try:
                user_input = input("Вы: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n👋 До свидания!")
                break

            if not user_input:
                continue

            if user_input == "/exit":
                print("👋 До свидания!")
                break

            if user_input == "/reset":
                agent.reset()
                print("🔄 История диалога сброшена.\n")
                continue

            try:
                if count_tokens([{"role": "user", "content": user_input}]) > 3000:
                    print("⚠️ Сообщение слишком длинное, сократите его.")
                    continue
                print("Агент: ", end="", flush=True)
                for chunk in agent.chat(user_input):
                    print(chunk, end="", flush=True)
                print()
            except Exception as exc:
                print(f"⚠️ Ошибка при обращении к модели: {exc}\n")
                continue

    finally:
        print("\n💾 Сохраняю историю в JSON")
        try:
            agent.history.save(history_file)
        except Exception as e:
            print(f"⚠️ Не удалось сохранить историю: {e}")


if __name__ == "__main__":
    main()