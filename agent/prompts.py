"""Шаблоны промптов. Пока один, но сюда легко добавлять новые роли."""

from config import SYSTEM_PROMPT

def build_system_prompt(extra: str | None = None) -> str:
    if extra:
        return f"{SYSTEM_PROMPT}\n\n{extra}"
    return SYSTEM_PROMPT