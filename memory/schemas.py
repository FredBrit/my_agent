from typing import Literal, TypedDict

class UserMessage(TypedDict):
    role: Literal["user"]
    content: str

class AssistantMessage(TypedDict, total=False):
    role: Literal["assistant"]
    content: str
    tool_calls: list[dict]

class ToolMessage(TypedDict):
    role: Literal["tool"]
    tool_call_id: str
    content: str

Message = UserMessage | AssistantMessage | ToolMessage