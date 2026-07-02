from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """Abstract base class for LLM Providers."""
    
    @abstractmethod
    def complete(self, prompt: str, text: str) -> str:
        """
        Takes a prompt and a document text, sends it to the LLM, 
        and returns the string response.
        """
        pass