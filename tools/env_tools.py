"""Инструменты для управления зависимостями (pip install)."""

import re
import subprocess
import sys

# Разрешённые символы для имени пакета: буквы, цифры, _, -, . и [extras]
_PACKAGE_RE = re.compile(r"^[a-zA-Z0-9_\-\.\[\]]+$")


def install_package(package: str) -> str:
    """Устанавливает Python-пакет через pip.

    package — имя пакета (например, 'fastapi', 'requests', 'pytest').
    Можно указать версию: 'fastapi==0.104.0'.
    НЕ поддерживает установку из файлов или URL — только из PyPI.
    """
    try:
        # 1. Базовая проверка на безопасность
        if not package or not _PACKAGE_RE.match(package):
            return (
                "Error: invalid package name. Only letters, digits, '-', '_', '.', and '[]' "
                "are allowed. No spaces, no command-line flags, no paths."
            )

        # 2. Запускаем pip install
        # --quiet — чтобы не засорять вывод
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", package],
            capture_output=True,
            text=True,
            timeout=120,  # установка может занять время
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if result.returncode == 0:
            return f"Success: package '{package}' installed or already satisfied."

        # Ошибка установки (например, нет такого пакета)
        error_msg = stderr or stdout or "unknown error"
        return f"Error installing '{package}':\n{error_msg[-1000:]}"  # последние 1000 символов

    except subprocess.TimeoutExpired:
        return f"Error: pip install for '{package}' timed out after 120s."
    except Exception as e:
        return f"Error running pip: {e}"


INSTALL_PACKAGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "install_package",
        "description": (
            "Install a Python package from PyPI using pip. "
            "Use this when you need to add a dependency (e.g., 'fastapi', 'pytest'). "
            "Accepts package names with optional version (e.g., 'fastapi==0.104.0'). "
            "Does NOT support -r requirements.txt or installing from URLs — "
            "use run_python if you need to install a requirements file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "package": {
                    "type": "string",
                    "description": "The name of the package to install (e.g., 'fastapi', 'pytest', 'requests==2.31.0').",
                },
            },
            "required": ["package"],
        },
    },
}