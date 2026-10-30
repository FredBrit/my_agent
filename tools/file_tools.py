"""Инструменты для работы с файловой системой: чтение, запись, правка, листинг."""

from pathlib import Path

# Максимальный размер файла, который read_file вернёт целиком.
# 30k символов ≈ 7-8k токенов. При num_ctx=32768 это безопасно,
# даже если в истории уже есть пара других файлов.
MAX_FILE_CHARS = 30_000

# Шумовые папки, которые не показываем по умолчанию в list_directory.
_NOISE_DIRS = {"__pycache__", "node_modules", "venv", "env", "dist", "build"}


# ────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ────────────────────────────────────────────────────────────────

def _human_size(n: int) -> str:
    """Байты → человекочитаемо: 1234 → '1.2 KB'."""
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB", "TB"):
        n /= 1024
        if n < 1024:
            return f"{n:.1f} {unit}"
    return f"{n:.1f} PB"


def _find_all_lines(content: str, needle: str) -> list[int]:
    """Номера строк, где встречается needle (может быть многострочным)."""
    lines: list[int] = []
    start = 0
    while True:
        idx = content.find(needle, start)
        if idx == -1:
            break
        lines.append(content[:idx].count("\n") + 1)
        start = idx + len(needle)
    return lines


def _not_found_hint(path: str, content: str, old_text: str) -> str:
    """Пытается угадать, где модель ошиблась с old_text."""
    first_line = old_text.split("\n", 1)[0].strip()
    if not first_line:
        return (
            f"Error: old_text not found in {path}. "
            f"The file may have been changed since you read it — call read_file to refresh."
        )

    candidates = [
        i for i, line in enumerate(content.splitlines(), 1)
        if first_line in line.strip()
    ]

    if candidates:
        return (
            f"Error: old_text not found EXACTLY in {path}. "
            f"Hint: a line containing {first_line!r} exists at lines {candidates[:5]}. "
            f"Likely cause: whitespace or indentation differs. "
            f"Copy the exact fragment from read_file output (preserving leading spaces)."
        )

    return (
        f"Error: old_text not found in {path}. "
        f"Call read_file to see the current content — the file may have changed."
    )


# ────────────────────────────────────────────────────────────────
# read_file
# ────────────────────────────────────────────────────────────────

def read_file(path: str) -> str:
    """Читает содержимое текстового файла и возвращает как строку.

    Если файл больше MAX_FILE_CHARS — возвращает только начало
    с явной пометкой об усечении.
    """
    try:
        file_path = Path(path).resolve()
        if not str(file_path).startswith(str(Path.cwd())):
            return "Error: Access denied. You can only read files in the current working directory."

        if not file_path.exists():
            return f"Error: File not found at {path}"

        if not file_path.is_file():
            return f"Error: {path} is not a regular file. Use list_directory to explore."

        content = file_path.read_text(encoding="utf-8")

        # Защита от гигантских файлов — они не влезут в контекст
        if len(content) > MAX_FILE_CHARS:
            return (
                f"{content[:MAX_FILE_CHARS]}\n\n"
                f"... [truncated: file is {len(content)} chars, showing first {MAX_FILE_CHARS}. "
                f"This file is too large to read at once. Use edit_file with a specific "
                f"old_text, or ask the user to narrow the scope.]"
            )

        return content

    except Exception as e:
        return f"Error reading file: {e}"


READ_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": (
            "Read the contents of a text file from the local filesystem. "
            "Use this when you need to understand the contents of a file before modifying it. "
            f"Files larger than {MAX_FILE_CHARS} chars are truncated with a notice. "
            "If truncated, work with the visible portion or ask the user to narrow the scope."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The relative path to the file, e.g. 'src/main.py'",
                },
            },
            "required": ["path"],
        },
    },
}


# ────────────────────────────────────────────────────────────────
# write_file
# ────────────────────────────────────────────────────────────────

def write_file(path: str, content: str) -> str:
    """Записывает строку в файл. Создаёт или перезаписывает."""
    try:
        file_path = Path(path).resolve()
        if not str(file_path).startswith(str(Path.cwd())):
            return "Error: Access denied. You can only write files in the current working directory."

        # Создаём родительские директории, если их нет
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Success: Content written to {path} ({len(content)} chars)."
    except Exception as e:
        return f"Error writing file: {e}"


WRITE_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": (
            "Write content to a file on the local filesystem. "
            "Creates the file or overwrites it if it already exists. "
            "For EDITING an existing file, prefer edit_file — it's safer and preserves the rest of the file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file, e.g. 'output/script.py'",
                },
                "content": {
                    "type": "string",
                    "description": "The full content to write into the file",
                },
            },
            "required": ["path", "content"],
        },
    },
}


# ────────────────────────────────────────────────────────────────
# edit_file
# ────────────────────────────────────────────────────────────────

def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Заменяет ТОЧНОЕ и УНИКАЛЬНОЕ вхождение old_text на new_text."""
    try:
        file_path = Path(path).resolve()
        if not str(file_path).startswith(str(Path.cwd())):
            return "Error: Access denied. You can only edit files in the current working directory."

        if not file_path.exists():
            return f"Error: File not found at {path}. Use write_file to create it first."

        if not file_path.is_file():
            return f"Error: {path} is not a regular file."

        if not old_text:
            return "Error: old_text cannot be empty."
        if old_text == new_text:
            return "Error: old_text and new_text are identical — nothing to replace."

        content = file_path.read_text(encoding="utf-8")
        count = content.count(old_text)

        if count == 0:
            return _not_found_hint(path, content, old_text)

        if count > 1:
            positions = _find_all_lines(content, old_text)
            return (
                f"Error: old_text found {count} times in {path} at lines {positions}. "
                f"Add more surrounding context to old_text to make it unique "
                f"(e.g., include the function signature or comment above)."
            )

        line_number = content[: content.index(old_text)].count("\n") + 1
        new_content = content.replace(old_text, new_text, 1)
        file_path.write_text(new_content, encoding="utf-8")

        delta = len(new_content) - len(content)
        sign = "+" if delta >= 0 else ""
        return (
            f"Success: Replaced 1 occurrence in {path} at line {line_number}. "
            f"File size: {len(content)} → {len(new_content)} chars ({sign}{delta})."
        )

    except Exception as e:
        return f"Error editing file: {e}"


EDIT_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": (
            "Edit an existing file by replacing a UNIQUE text fragment. "
            "old_text must match EXACTLY — including whitespace, indentation, "
            "quotes and line endings. "
            "If old_text appears more than once, the edit is REJECTED — "
            "include more surrounding context to make it unique. "
            "ALWAYS call read_file first to copy the exact fragment. "
            "For creating a new file, use write_file instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file, e.g. 'src/main.py'",
                },
                "old_text": {
                    "type": "string",
                    "description": (
                        "Exact fragment to find. Must be unique in the file. "
                        "Include enough surrounding lines (2-3) to disambiguate. "
                        "Preserve the original indentation."
                    ),
                },
                "new_text": {
                    "type": "string",
                    "description": (
                        "Replacement text. Use an empty string '' to DELETE old_text. "
                        "Preserve the indentation of the original."
                    ),
                },
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
}


# ────────────────────────────────────────────────────────────────
# list_directory
# ────────────────────────────────────────────────────────────────

def list_directory(path: str = ".", show_hidden: bool = False, depth: int = 1) -> str:
    """Список файлов и подпапок до указанной глубины.

    depth: 1 = только эта папка, 2 = + подпапки, 3 = + под-подпапки.
    """
    try:
        dir_path = Path(path).resolve()
        if not str(dir_path).startswith(str(Path.cwd())):
            return "Error: Access denied. You can only list directories in the current working directory."

        if not dir_path.exists():
            return f"Error: Directory not found at {path}"

        if not dir_path.is_dir():
            return f"Error: {path} is not a directory. Use read_file to read files."

        depth = max(1, min(int(depth), 3))

        MAX_ENTRIES = 300
        entries: list[str] = []
        truncated = False

        def walk(current: Path, remaining: int, indent: str) -> None:
            nonlocal truncated
            if remaining <= 0 or truncated:
                return

            try:
                items = sorted(
                    current.iterdir(),
                    key=lambda x: (not x.is_dir(), x.name.lower()),
                )
            except PermissionError:
                entries.append(f"{indent}[permission denied]")
                return

            for item in items:
                if truncated:
                    return

                name = item.name

                if not show_hidden:
                    if name.startswith("."):
                        continue
                    if item.is_dir() and name in _NOISE_DIRS:
                        continue

                if item.is_dir():
                    entries.append(f"{indent}DIR  {name}/")
                    if len(entries) >= MAX_ENTRIES:
                        truncated = True
                        return
                    walk(item, remaining - 1, indent + "  ")
                else:
                    try:
                        size = _human_size(item.stat().st_size)
                    except OSError:
                        size = "?"
                    entries.append(f"{indent}FILE {name} ({size})")
                    if len(entries) >= MAX_ENTRIES:
                        truncated = True
                        return

        walk(dir_path, depth, "")

        if not entries:
            suffix = "" if show_hidden else " (hidden/noise entries skipped; try show_hidden=true)"
            return f"Directory {path} is empty{suffix}."

        parts = [f"{path} (depth={depth}):", *entries]
        if truncated:
            parts.append(f"... truncated at {MAX_ENTRIES} entries. Use a more specific path.")
        return "\n".join(parts)

    except Exception as e:
        return f"Error listing directory: {e}"


LIST_DIRECTORY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_directory",
        "description": (
            "List files and subdirectories up to a given depth. "
            "Start with default (depth=1) to see the top level — then increase depth "
            "or pass a specific path if you need more. "
            "Hidden files (.git, .env) and noise dirs (__pycache__, node_modules, venv) "
            "are skipped by default. "
            "Output: 'DIR  name/' for dirs, 'FILE name (size)' for files, "
            "indented 2 spaces per level. Max 300 entries per call."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the directory. '.' or omit for the current working directory.",
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": (
                        "If true, include hidden ('.*') and noise (__pycache__, node_modules) entries. "
                        "Default: false."
                    ),
                },
                "depth": {
                    "type": "integer",
                    "description": (
                        "Recursion depth. 1 = only this directory (default), "
                        "2 = include subdirectories, 3 = include sub-subdirectories. "
                        "Values above 3 are clamped to 3."
                    ),
                },
            },
            "required": [],
        },
    },
}