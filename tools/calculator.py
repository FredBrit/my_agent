
def add(a: float, b: float) -> float:
    """Складывает два числа."""
    return a + b

def multiply(a: float, b: float) -> float:
    """Умножает два числа."""
    return a * b

ADD_SCHEMA = {
    "type": "function",
    "function": {
        "name": "add",
        "description": "Складывает два числа",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "Первое число"},
                "b": {"type": "number", "description": "Второе число"},
            },
            "required": ["a", "b"],
        },
    },
}

MULTIPLY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "multiply",
        "description": "Умножает два числа",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "Первое число"},
                "b": {"type": "number", "description": "Второе число"},
            },
            "required": ["a", "b"],
        },
    },
}