"""Инструмент для запуска Python-кода в изолированной папке sandbox/."""

import subprocess
import sys
from pathlib import Path

DEFAULT_TIMEOUT = 10
MAX_TIMEOUT = 60

# Ограничение на размер вывода — иначе модель может получить
# мегабайты логов и забить контекст
MAX_OUTPUT_CHARS = 5000


def _get_sandbox_dir() -> Path:
    """Возвращает путь к папке sandbox/ ОТНОСИТЕЛЬНО ТЕКУЩЕЙ рабочей директории.
    
    ВАЖНО: мы не храним это в глобальной переменной, потому что
    evals/run_evals.py может менять cwd (os.chdir) во время работы.
    """
    return Path.cwd() / "sandbox"


def run_python(path: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Запускает Python-файл из sandbox/ и возвращает stdout/stderr + код выхода.

    path — путь ОТНОСИТЕЛЬНО sandbox/, например "fibonacci.py" или "tests/test_x.py".
    Только .py-файлы внутри sandbox/. Абсолютные пути вне sandbox отклоняются.
    """
    try:
        sandbox_dir = _get_sandbox_dir()
        sandbox_dir.mkdir(exist_ok=True)

        # ── 2. Нормализация: принимаем и "fibonacci.py", и "sandbox/fibonacci.py" ──
        raw = Path(path)
        if raw.parts and raw.parts[0].lower() == "sandbox":
            raw = Path(*raw.parts[1:])  # отрезаем первый компонент

        file_path = (sandbox_dir / raw).resolve()

        # Проверка песочницы: путь должен остаться внутри sandbox/
        if not file_path.is_relative_to(sandbox_dir.resolve()):
            return f"Error: run_python only works with files inside {sandbox_dir.name}/"

        if not file_path.exists():
            return f"Error: File not found at {path} (relative to sandbox/). Use write_file to create it first."

        if not file_path.is_file():
            return f"Error: {path} is not a regular file."

        if file_path.suffix != ".py":
            return f"Error: only .py files can be run. Got: {file_path.suffix or '(no extension)'}"

        timeout = max(1, min(int(timeout), MAX_TIMEOUT))

        # ── 4. Запускаем ───────────────────────────────────────
        try:
            result = subprocess.run(
                [sys.executable, str(file_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=sandbox_dir,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return (
                f"Error: execution timed out after {timeout}s. "
                f"The script may have an infinite loop or be waiting for input. "
                f"Check the code and try again — or increase timeout up to {MAX_TIMEOUT}s."
            )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if len(stdout) > MAX_OUTPUT_CHARS:
            stdout = stdout[:MAX_OUTPUT_CHARS] + f"\n... [truncated, total {len(stdout)} chars]"
        if len(stderr) > MAX_OUTPUT_CHARS:
            stderr = stderr[:MAX_OUTPUT_CHARS] + f"\n... [truncated, total {len(stderr)} chars]"

        if result.returncode == 0:
            if stdout:
                return f"Success (exit 0):\n{stdout}"
            return "Success (exit 0, no output)"

        parts = [f"Failed (exit {result.returncode}):"]
        if stdout:
            parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            parts.append(f"STDERR:\n{stderr}")
        return "\n\n".join(parts)

    except Exception as e:
        return f"Error running python: {e}"


RUN_PYTHON_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_python",
        "description": (
            "Execute a Python file from sandbox/ and return its output (stdout/stderr + exit code). "
            "Use this to VERIFY code you wrote or edited — always test before claiming success. "
            "Path can be 'fibonacci.py' OR 'sandbox/fibonacci.py' — both accepted. "
            f"Only .py files inside sandbox/ can be run. Default timeout {DEFAULT_TIMEOUT}s, max {MAX_TIMEOUT}s. "
            "The script runs WITHOUT stdin — input() will fail. "
            "If it fails, read the error, fix via edit_file, and run again."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path to .py file. Can be either relative to sandbox/ "
                        "('fibonacci.py') OR with 'sandbox/' prefix ('sandbox/fibonacci.py') — "
                        "both work. Paths outside sandbox/ are rejected."
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        f"Timeout in seconds (1-{MAX_TIMEOUT}, default {DEFAULT_TIMEOUT}). "
                        f"Increase only if the script legitimately needs more time."
                    ),
                },
            },
            "required": ["path"],
        },
    },
}