"""Инструменты для поиска по файлам и чтения по диапазону строк."""

from pathlib import Path

# Игнорируем шумовые папки при поиске
_NOISE_DIRS = {"__pycache__", "node_modules", "venv", "env", "dist", "build", ".git", ".venv"}

MAX_SEARCH_RESULTS = 50
MAX_LINE_LENGTH = 200

def search_in_files(query: str, path: str = ".", case_sensitive: bool = False) -> str:
    """Ищет подстроку во всех текстовых файлах рекурсивно (аналог grep -rn)."""
    try:
        base_path = Path(path).resolve()
        if not str(base_path).startswith(str(Path.cwd())):
            return "Error: Access denied. You can only search in the current working directory."
        
        if not base_path.exists():
            return f"Error: Path not found: {path}"

        results: list[str] = []
        total_matches = 0

        # Собираем все файлы для поиска
        if base_path.is_file():
            files_to_search = [base_path]
        else:
            files_to_search = []
            for p in base_path.rglob("*"):
                if p.is_file():
                    # Пропускаем шум и бинарники
                    if any(part in _NOISE_DIRS for part in p.parts):
                        continue
                    if p.suffix in {".pyc", ".png", ".jpg", ".zip", ".exe"}:
                        continue
                    files_to_search.append(p)

        needle = query if case_sensitive else query.lower()

        for file_path in files_to_search:
            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue  # пропускаем бинарные или недоступные файлы

            for i, line in enumerate(content.splitlines(), 1):
                haystack = line if case_sensitive else line.lower()
                if needle in haystack:
                    total_matches += 1
                    rel_path = file_path.relative_to(Path.cwd())
                    
                    # Обрезаем очень длинные строки
                    display_line = line.strip()
                    if len(display_line) > MAX_LINE_LENGTH:
                        display_line = display_line[:MAX_LINE_LENGTH] + "..."
                    
                    results.append(f"{rel_path}:{i}: {display_line}")
                    
                    if total_matches >= MAX_SEARCH_RESULTS:
                        results.append(f"... [truncated at {MAX_SEARCH_RESULTS} matches]")
                        return "\n".join(results)

        if not results:
            return f"No matches found for {query!r} in {path}"
        
        return f"Found {total_matches} matches:\n" + "\n".join(results)

    except Exception as e:
        return f"Error searching files: {e}"


SEARCH_IN_FILES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_in_files",
        "description": (
            "Recursively search for a text string in all files (like 'grep -rn'). "
            "Use this to find where a function is defined, where an import is used, etc. "
            "Skips binary files and noise directories (__pycache__, .git, node_modules). "
            f"Returns file:line: content. Max {MAX_SEARCH_RESULTS} results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The text to search for (e.g., 'def fibonacci', 'import fastapi')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search in. Defaults to '.' (current dir).",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "If true, match case exactly. Default: false.",
                },
            },
            "required": ["query"],
        },
    },
}


def read_file_range(path: str, start_line: int, end_line: int) -> str:
    """Читает конкретный диапазон строк из файла (с 1-индексацией)."""
    try:
        file_path = Path(path).resolve()
        if not str(file_path).startswith(str(Path.cwd())):
            return "Error: Access denied."
        
        if not file_path.exists() or not file_path.is_file():
            return f"Error: File not found: {path}"

        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        total_lines = len(lines)
        start_line = max(1, start_line)
        end_line = min(total_lines, end_line)

        if start_line > end_line:
            return f"Error: start_line ({start_line}) is greater than end_line ({end_line})."

        # Форматируем с номерами строк, чтобы модели было проще ориентироваться
        result = [f"--- {path} (lines {start_line}-{end_line} of {total_lines}) ---"]
        for i in range(start_line - 1, end_line):
            result.append(f"{i+1:4d} | {lines[i]}")

        return "\n".join(result)

    except Exception as e:
        return f"Error reading file range: {e}"


READ_FILE_RANGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file_range",
        "description": (
            "Read a specific range of lines from a file (1-indexed). "
            "Use this when you know roughly where the code is (e.g., after search_in_files) "
            "but the file is too large to read entirely. "
            "Prints line numbers alongside content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file."},
                "start_line": {"type": "integer", "description": "First line to read (1-indexed)."},
                "end_line": {"type": "integer", "description": "Last line to read (inclusive)."},
            },
            "required": ["path", "start_line", "end_line"],
        },
    },
}