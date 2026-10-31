import json

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.app.core.config import get_settings
from backend.app.llm.base import LLMResult, ToolCall


def cost_usd(tokens_in: int, tokens_out: int) -> float:
    s = get_settings()
    return tokens_in / 1e6 * s.llm_price_in_per_m + tokens_out / 1e6 * s.llm_price_out_per_m


class DeepSeekClient:
    def __init__(self):
        s = get_settings()
        self.c = OpenAI(api_key=s.deepseek_api_key, base_url=s.deepseek_base_url, timeout=90)
        self.default_model = s.llm_model_fast

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def chat(
        self,
        messages,
        *,
        tools=None,
        json_mode=False,
        temperature=0.0,
        model=None,
        max_tokens=2000,
    ) -> LLMResult:
        kw = dict(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kw["tools"] = tools
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        r = self.c.chat.completions.create(**kw)
        m = r.choices[0].message
        calls = [
            ToolCall(tc.id, tc.function.name, json.loads(tc.function.arguments or "{}"))
            for tc in (m.tool_calls or [])
        ]
        return LLMResult(
            m.content,
            calls,
            r.usage.prompt_tokens if r.usage else 0,
            r.usage.completion_tokens if r.usage else 0,
            m.model_dump(exclude_none=True),
        )


class FakeLLM:
    """Offline stand-in returning canned JSON. Used by tests and mock mode."""

    def __init__(self, responses: list[LLMResult] | None = None):
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    def chat(
        self,
        messages,
        *,
        tools=None,
        json_mode=False,
        temperature=0.0,
        model=None,
        max_tokens=2000,
    ) -> LLMResult:
        self.calls.append({"messages": messages, "tools": tools, "json_mode": json_mode})
        if self.responses:
            return self.responses.pop(0)
        content = (
            json.dumps({"route": "out_of_scope", "standalone_question": "", "reason": "mock"})
            if json_mode
            else "FakeLLM response"
        )
        return LLMResult(content=content)


def get_llm():
    s = get_settings()
    if s.use_mock_llm or not s.deepseek_api_key:
        return FakeLLM()
    if s.llm_provider == "deepseek":
        return DeepSeekClient()
    return DeepSeekClient()

