"""Точный подсчёт токенов для Qwen 3.5 через Hugging Face."""

from functools import lru_cache

from transformers import AutoTokenizer

_QWEN_TOKENIZER_ID = "Qwen/Qwen3.5-9B"


@lru_cache(maxsize=1)
def _get_tokenizer() -> "AutoTokenizer":
    """Ленивая загрузка токенизатора. Один раз на процесс."""
    return AutoTokenizer.from_pretrained(_QWEN_TOKENIZER_ID)


def count_tokens(messages: list[dict]) -> int:
    """Считает число токенов в списке сообщений формата OpenAI.

    Основной путь — apply_chat_template (точный шаблон Qwen).
    Fallback — если шаблон не может отрендериться (например, история
    содержит только assistant-сообщения, как в пробных вариантах trim).
    """
    tokenizer = _get_tokenizer()

    try:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        return len(tokenizer(text, return_tensors=None)["input_ids"])
    except Exception:
        # Fallback: считаем каждое сообщение отдельно + приблизительный
        # overhead на role-маркеры (<|im_start|>role\n ... <|im_end|>\n).
        total = 0
        for m in messages:
            content = m.get("content") or ""
            if m.get("tool_calls"):
                content += " " + " ".join(
                    tc["function"]["arguments"] for tc in m["tool_calls"]
                )
            total += len(tokenizer(content, return_tensors=None)["input_ids"])
            total += 4  # overhead на служебные токены роли
        return total