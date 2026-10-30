from memory.tokenizer import count_tokens
from memory.history import ConversationHistory

# 1. Базовый подсчёт
msgs = [
    {"role": "system", "content": "Ты — ассистент."},
    {"role": "user", "content": "Сколькими способами можно достичь числа 100, если у насть есть числа 10 и 2?"},
]
print("Токенов в messages:", count_tokens(msgs))

# 2. Проверка trim
h = ConversationHistory("Ты — ассистент.")
for i in range(30):
    h.add_user_msg(f"Вопрос номер {i}: " + "очень длинный текст " * 20)
    h.add_assistant_msg(type("M", (), {"content": f"Ответ {i}", "tool_calls": None})())

print("До trim:", len(h), "сообщений,", count_tokens(h.messages), "токенов")
h.trim(max_tokens=1000)
print("После trim:", len(h), "сообщений,", count_tokens(h.messages), "токенов")