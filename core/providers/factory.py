from core.providers.base import LLMProvider
from core.providers.gemini import GeminiProvider

def get_provider(name: str) -> LLMProvider:
    """
    Factory function to get the requested LLM provider instance.
    """
    if name.lower() == "gemini":
        return GeminiProvider()
    else:
        raise NotImplementedError(f"LLM Provider '{name}' is not currently supported. Only 'gemini' is available in V1.")