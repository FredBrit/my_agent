"""Управление историей диалога. Сейчас — в памяти, потом можно в файл/БД."""

import json
from pathlib import Path

from memory.schemas import Message
from memory.tokenizer import count_tokens


class ConversationHistory:
    """Хранит сообщения в формате, который понимает OpenAI API."""

    def __init__(self, system_prompt: str):
        # system-промпт храним ОТДЕЛЬНО от _messages — чтобы можно было
        # восстановить даже после clear(keep_system=False)
        self._system_prompt = system_prompt
        self._messages: list[Message] = [
            {"role": "system", "content": system_prompt}
        ]

    def __len__(self) -> int:
        # Позволяет писать len(history) — удобно в отладке
        return len(self._messages)

    def __repr__(self) -> str:
        # Компактное представление для print() и REPL
        return (
            f"ConversationHistory(messages={len(self)}, "
            f"last_role={self._messages[-1]['role'] if self._messages else None})"
        )

    @property
    def system_prompt(self) -> str:
        # Публичное свойство-обёртка над _system_prompt.
        # Внешний код не должен лезть в приватное поле напрямую.
        return self._system_prompt

    def add_user_msg(self, content: str) -> None:
        # Валидация на входе — ловим ошибку там, где она случилась
        if not isinstance(content, str) or not content.strip():
            raise ValueError("user message must be a non-empty string")
        self._messages.append({"role": "user", "content": content})

    def add_assistant_msg(self, msg) -> None:
        """Совместимость с non-streaming: принимает Pydantic-объект."""
        if getattr(msg, "tool_calls", None):
            tcs = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        else:
            tcs = []
        self.add_assistant_parts(msg.content or "", tcs)

    def add_assistant_parts(self, content: str, tool_calls: list[dict]) -> None:
        """Сохраняет assistant-сообщение из уже собранных частей (для streaming)."""
        entry: dict = {"role": "assistant", "content": content or ""}
        if tool_calls:
            entry["tool_calls"] = tool_calls
        self._messages.append(entry)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """Добавляет результат выполнения инструмента.

        Проверяет, что tool_call_id действительно запрашивался последним
        assistant(tool_calls) — иначе Ollama вернёт 400.
        """
        pending_ids = set()
        for m in reversed(self._messages):
            if m["role"] == "assistant" and m.get("tool_calls"):
                pending_ids = {tc["id"] for tc in m["tool_calls"]}
                break

        if tool_call_id not in pending_ids:
            raise ValueError(f"unknown tool_call_id: {tool_call_id}")

        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })

    @property
    def messages(self) -> list[Message]:
        """Возвращает копию, чтобы случайно не изменить историю извне."""
        return list(self._messages)

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(self._messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def trim(self, max_tokens: int = 3000) -> int:
        """Обрезает историю с начала, оставляя system + самые свежие сообщения.

        Возвращает количество УДАЛЁННЫХ сообщений (0 = ничего не резали).
        Это нужно, чтобы вызывающий код мог предупредить пользователя,
        что контекст «просел» и модель могла что-то забыть.

        Режет только по безопасным границам: не разрывает пары
        assistant(tool_calls) ↔ tool.
        """
        # Нечего резать — только system
        if len(self._messages) <= 1:
            return 0

        # Быстрый путь: всё влезает целиком
        if count_tokens(self._messages) <= max_tokens:
            return 0

        original_len = len(self._messages)

        # Идём с конца, копим сообщения, пока не упрёмся в лимит.
        # system (индекс 0) всегда оставляем.
        kept: list[dict] = []
        cut_index = 1

        for i in range(len(self._messages) - 1, 0, -1):
            msg = self._messages[i]
            trial = [self._messages[0]] + [msg] + kept
            if count_tokens(trial) > max_tokens:
                cut_index = i + 1
                break
            kept.insert(0, msg)
        else:
            # Крайний случай: даже одно последнее сообщение не влезает
            cut_index = len(self._messages) - 1

        # Корректируем границу, чтобы не разорвать tool-пары
        cut_index = self._safe_cut(cut_index)

        # Применяем
        self._messages = [self._messages[0]] + self._messages[cut_index:]

        # Возвращаем, сколько удалили
        return original_len - len(self._messages)

    def _safe_cut(self, cut_index: int) -> int:
        """Сдвигает границу, если она оставляет сироту tool без запроса."""
        if cut_index <= 1:
            return 1

        # Если сразу после границы стоит tool — его assistant(tool_calls)
        # остался «за бортом». Сдвигаем границу вправо, пока не съедим все tool.
        while cut_index < len(self._messages) and self._messages[cut_index]["role"] == "tool":
            cut_index += 1

        # Если ПЕРЕД границей стоит tool — сдвигаем границу влево,
        # чтобы tool ушёл вместе с assistant.
        while cut_index > 1 and self._messages[cut_index - 1]["role"] == "tool":
            cut_index -= 1

        return cut_index

    @classmethod
    def load(
        cls,
        path: Path,
        system_prompt: str | None = None,
    ) -> "ConversationHistory":
        """Загружает историю из JSON-файла.

        system_prompt — если передан, ЗАМЕНЯЕТ старый system из файла.
        Это позволяет менять «характер» агента в config.py, не теряя память.
        """
        data = json.loads(path.read_text(encoding="utf-8"))

        if not isinstance(data, list) or not data or data[0].get("role") != "system":
            raise ValueError(f"invalid history file: {path}")

        prompt = system_prompt or data[0]["content"]

        h = cls(system_prompt=prompt)
        h._messages = data
        h._messages[0] = {"role": "system", "content": prompt}
        return h

    def clear(self, keep_system: bool = True) -> None:
        if keep_system:
            self._messages = [{"role": "system", "content": self._system_prompt}]
        else:
            self._messages = []