from core.providers.base import LLMProvider
from core.providers.gemini import GeminiProvider
from core.providers.groq_provider import GroqProvider

def get_provider(name: str) -> LLMProvider:
    """
    Factory function to get the requested LLM provider instance.
    """
    if name.lower() == "gemini":
        return GeminiProvider()
    elif name.lower() == "groq":
        return GroqProvider()
    else:
        raise NotImplementedError(f"LLM Provider '{name}' is not currently supported.")