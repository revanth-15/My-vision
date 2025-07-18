"""
JARVIS — AI service layer.

The whole point of this file: every provider exposes the same `chat()` method,
so swapping Groq for Ollama for Together.AI is a one-line change in .env and
nothing else in the codebase moves. Raw `requests` is used instead of vendor
SDKs so there is no SDK version to break.
"""

from datetime import datetime

import requests

SYSTEM_TEMPLATE = """You are {assistant}, a sophisticated AI assistant in the style of Tony Stark's JARVIS.

Voice and manner:
- Composed, precise, quietly witty. Never sycophantic, never over-eager.
- Address the user as "{user}".
- Answers are short by default. Expand only when the question earns it.
- Plain sentences. No bullet lists unless the content is genuinely a list.
- Your replies are often read aloud by a speech synthesiser, so avoid markdown
  symbols, emoji and ASCII art in normal conversation.

Current date and time: {timestamp}

What you already know from stored memory:
{memory}

If the user asks about their tasks, events or notes, answer from the memory
above rather than guessing. If the memory does not contain the answer, say so
plainly."""


class AIError(RuntimeError):
    """Raised when the upstream model cannot be reached or refuses the call."""


# --------------------------------------------------------------------- base
class BaseAIService:
    name = "base"

    def __init__(self, config):
        self.config = config

    def build_system_prompt(self, memory_context: str) -> str:
        return SYSTEM_TEMPLATE.format(
            assistant=self.config.ASSISTANT_NAME,
            user=self.config.USER_NAME,
            timestamp=datetime.now().strftime("%A, %d %B %Y, %H:%M"),
            memory=memory_context,
        )

    def build_messages(self, user_message, history, memory_context) -> list:
        messages = [
            {"role": "system", "content": self.build_system_prompt(memory_context)}
        ]
        for turn in history or []:
            if turn.get("role") in {"user", "assistant"} and turn.get("content"):
                messages.append(
                    {"role": turn["role"], "content": turn["content"]}
                )
        messages.append({"role": "user", "content": user_message})
        return messages

    def chat(self, user_message, history=None, memory_context="") -> str:
        raise NotImplementedError

    def health(self) -> dict:
        return {"provider": self.name, "ok": True, "detail": "not checked"}


# --------------------------------------------------------- OpenAI-compatible
class _OpenAICompatibleService(BaseAIService):
    """Shared implementation for Groq and Together, which both speak the
    OpenAI chat-completions dialect."""

    base_url = ""
    api_key = ""
    model = ""

    def chat(self, user_message, history=None, memory_context="") -> str:
        if not self.api_key:
            raise AIError(
                f"No API key set for {self.name}. Add it to backend/.env and restart."
            )

        payload = {
            "model": self.model,
            "messages": self.build_messages(user_message, history, memory_context),
            "max_tokens": self.config.MAX_TOKENS,
            "temperature": self.config.TEMPERATURE,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=self.config.REQUEST_TIMEOUT,
            )
        except requests.exceptions.Timeout:
            raise AIError(f"{self.name} timed out. Try again in a moment.")
        except requests.exceptions.RequestException as exc:
            raise AIError(f"Could not reach {self.name}: {exc}")

        if resp.status_code == 401:
            raise AIError(f"{self.name} rejected the API key. Check backend/.env.")
        if resp.status_code == 429:
            raise AIError(
                f"{self.name} rate limit reached. Wait a minute, or switch "
                "AI_PROVIDER in .env."
            )
        if resp.status_code == 404:
            raise AIError(
                f"Model '{self.model}' was not found on {self.name}. It may have "
                "been retired — set a current model in .env."
            )
        if resp.status_code >= 400:
            raise AIError(f"{self.name} returned {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except (ValueError, KeyError, IndexError):
            raise AIError(f"Unexpected response shape from {self.name}.")

    def health(self) -> dict:
        return {
            "provider": self.name,
            "model": self.model,
            "ok": bool(self.api_key),
            "detail": "key present" if self.api_key else "API key missing in .env",
        }


class GroqService(_OpenAICompatibleService):
    """Free tier, fastest cloud option. https://console.groq.com"""

    name = "groq"

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.GROQ_BASE_URL
        self.api_key = config.GROQ_API_KEY
        self.model = config.GROQ_MODEL


class TogetherService(_OpenAICompatibleService):
    """Free tier with a monthly token allowance. https://api.together.xyz"""

    name = "together"

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.TOGETHER_BASE_URL
        self.api_key = config.TOGETHER_API_KEY
        self.model = config.TOGETHER_MODEL


# -------------------------------------------------------------------- local
class OllamaService(BaseAIService):
    """Runs entirely on your own machine. No key, no quota, nothing leaves
    the laptop. https://ollama.com"""

    name = "ollama"

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.OLLAMA_BASE_URL.rstrip("/")
        self.model = config.OLLAMA_MODEL

    def chat(self, user_message, history=None, memory_context="") -> str:
        payload = {
            "model": self.model,
            "messages": self.build_messages(user_message, history, memory_context),
            "stream": False,
            "options": {
                "temperature": self.config.TEMPERATURE,
                "num_predict": self.config.MAX_TOKENS,
            },
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.config.REQUEST_TIMEOUT,
            )
        except requests.exceptions.ConnectionError:
            raise AIError(
                "Ollama is not running. Start it with 'ollama serve', then "
                f"'ollama pull {self.model}'."
            )
        except requests.exceptions.Timeout:
            raise AIError("Ollama timed out. A local model can be slow on first run.")
        except requests.exceptions.RequestException as exc:
            raise AIError(f"Could not reach Ollama: {exc}")

        if resp.status_code >= 400:
            raise AIError(f"Ollama returned {resp.status_code}: {resp.text[:300]}")

        try:
            return resp.json()["message"]["content"].strip()
        except (ValueError, KeyError):
            raise AIError("Unexpected response shape from Ollama.")

    def health(self) -> dict:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=4)
            models = [m["name"] for m in resp.json().get("models", [])]
            pulled = any(m.split(":")[0] == self.model.split(":")[0] for m in models)
            return {
                "provider": self.name,
                "model": self.model,
                "ok": pulled,
                "detail": "model ready"
                if pulled
                else f"run 'ollama pull {self.model}'",
            }
        except Exception:
            return {
                "provider": self.name,
                "model": self.model,
                "ok": False,
                "detail": "Ollama not reachable — run 'ollama serve'",
            }


# ------------------------------------------------------------------ factory
PROVIDERS = {
    "groq": GroqService,
    "ollama": OllamaService,
    "together": TogetherService,
}


def get_ai_service(config) -> BaseAIService:
    """Single place the rest of the app calls. Change AI_PROVIDER in .env and
    every other file stays exactly as it is."""
    provider = PROVIDERS.get(config.AI_PROVIDER)
    if provider is None:
        raise AIError(
            f"Unknown AI_PROVIDER '{config.AI_PROVIDER}'. "
            f"Choose one of: {', '.join(PROVIDERS)}."
        )
    return provider(config)
