"""Ядро агента: обёртка над клиентом OpenAI, работающим с Ollama."""

import json
from collections.abc import Generator
from pathlib import Path

from openai import OpenAI

from config import (
    OLLAMA_API_KEY,
    OLLAMA_BASE_URL,
    MODEL_NAME,
    TEMPERATURE,
    MAX_TOKENS,
    NUM_CTX,          
    TRIM_MAX_TOKENS,  
)
from agent.prompts import build_system_prompt
from agent.tools import SCHEMAS, REGISTRY
from memory.history import ConversationHistory


def _format_tool_call(tc: dict) -> str:
    """Компактный JSON-дамп tool_call для отладки."""
    try:
        args = json.loads(tc["function"]["arguments"])
    except (json.JSONDecodeError, KeyError, TypeError):
        args = (tc.get("function") or {}).get("arguments", "")

    compact = {
        "id": tc["id"],
        "type": tc["type"],
        "function": {
            "name": tc["function"]["name"],
            "arguments": args,
        },
    }
    return json.dumps(compact, ensure_ascii=False, separators=(",", ":"))


class Agent:
    def __init__(self, system_prompt: str | None = None):
        # base_url перенаправляет клиент OpenAI на Ollama.
        # timeout — с запасом на холодный старт модели в VRAM.
        self.client = OpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key=OLLAMA_API_KEY,
            timeout=300.0,
        )
        self.history = ConversationHistory(
            system_prompt=system_prompt or build_system_prompt()
        )

    @classmethod
    def load(cls, path: Path, system_prompt: str | None = None) -> "Agent":
        """Создаёт агента с историей, загруженной из файла."""
        agent = cls(system_prompt)
        # Передаём АКТУАЛЬНЫЙ system-промпт — чтобы старая история
        # не воскрешала старый промпт из файла
        agent.history = ConversationHistory.load(
            path,
            system_prompt=agent.history.system_prompt,
        )
        return agent

    def chat(
        self,
        user_message: str,
        *,
        show_tool_calls: bool = True,
    ) -> Generator[str, None, None]:
        """Стриминговый чат: yield'ит куски текста по мере генерации.

        Tool calling обрабатывается внутри: если модель просит инструмент,
        агент выполняет его и продолжает цикл. Наружу это видно только
        через маркеры [🔧 ...] (если show_tool_calls=True).
        """
        self.history.add_user_msg(user_message)

        # HTTP-запрос к Ollama
        # response - это Pydantic-модель ChatCompletion
        # ├── id: str                     # "chatcmpl-..."
        # ├── object: "chat.completion"
        # ├── created: int                # Unix timestamp
        # ├── model: str                  # "qwen3.5:9b"
        # ├── choices: list[Choice]       # обычно один элемент
        # │   └── [0]
        # │       ├── index: int          # 0
        # │       ├── finish_reason: str  # "stop" | "length" | "tool_calls" | ...
        # │       ├── logprobs: ...       # если запросили
        # │       └── message: Message    # ← главное
        # │           ├── role: "assistant"
        # │           ├── content: str | None
        # │           ├── tool_calls: list[ToolCall] | None
        # │           ├── refusal: str | None
        # │           └── annotations: list | None
        # └── usage: object
        #     ├── prompt_tokens: int
        #     ├── completion_tokens: int
        #     └── total_tokens: int
        #
        # ПРИ СТРИМИНГЕ вместо одного response — поток чанков (stream).
        # Каждый chunk содержит delta (приращение) вместо message (готового).
        while True:
            # trim — обрезаем историю, чтобы не выйти за num_ctx модели.
            # Возвращает число удалённых сообщений — предупреждаем пользователя,
            # если модель что-то «забыла».
            removed = self.history.trim(max_tokens=TRIM_MAX_TOKENS)
            if removed and show_tool_calls:
                yield f"\n[⚠️ Обрезано {removed} старых сообщений — контекст переполнен]\n"

            stream = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=self.history.messages,
                tools=SCHEMAS,
                tool_choice="auto",
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                stream=True,
                stream_options={"include_usage": True},
                extra_body={
                    "think": False,
                    "reasoning_effort": "none",
                    # num_ctx — размер контекстного окна модели.
                    # Без этого Ollama использует дефолт (обычно 4096),
                    # и длинные истории молча обрезаются.
                    "options": {"num_ctx": NUM_CTX},
                },
            )

            # Аккумуляторы для текущей итерации
            content_parts: list[str] = []
            tool_calls_buffer: dict[int, dict] = {}

            for chunk in stream:
                if not chunk.choices:
                    # Чанк только с usage (финальный)
                    continue

                delta = chunk.choices[0].delta

                # Текстовый кусок — сразу yield
                if delta.content:
                    content_parts.append(delta.content)
                    yield delta.content

                # Фрагменты tool_calls — склеиваем по index,
                # потому что arguments приходят порезанными
                if delta.tool_calls:
                    for frag in delta.tool_calls:
                        # index может быть None (некоторые версии Ollama)
                        idx = frag.index if frag.index is not None else len(tool_calls_buffer)

                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }

                        buf = tool_calls_buffer[idx]

                        # id и name приходят целиком, arguments — по кускам
                        if frag.id:
                            buf["id"] = frag.id
                        if frag.function:
                            if frag.function.name:
                                buf["function"]["name"] += frag.function.name
                            if frag.function.arguments:
                                buf["function"]["arguments"] += frag.function.arguments

            content = "".join(content_parts)

            # НЕТ tool_calls — модель закончила ответом
            if not tool_calls_buffer:
                self.history.add_assistant_parts(content, [])
                return

            # ЕСТЬ tool_calls — сохраняем и выполняем
            tool_calls_list = [tool_calls_buffer[i] for i in sorted(tool_calls_buffer)]
            self.history.add_assistant_parts(content, tool_calls_list)

            for tc in tool_calls_list:
                name = tc["function"]["name"]
                raw_args = tc["function"]["arguments"]

                if show_tool_calls:
                    yield f"\n[🔧 {_format_tool_call(tc)}"

                func = REGISTRY.get(name)
                if func is None:
                    result = f"error: unknown tool '{name}'"
                else:
                    try:
                        args = json.loads(raw_args)
                        result = str(func(**args))
                    except Exception as exc:
                        result = f"error: {exc}"

                if show_tool_calls:
                    yield f" → {result}]\n"

                # Сохраняем результат с тем же tool_call_id — связка для API
                self.history.add_tool_result(tc["id"], result)

            # → возвращаемся в начало while: модель получит результаты

    def reset(self) -> None:
        """Сбрасывает историю диалога (системный промпт сохраняется)."""
        self.history.clear(keep_system=True)