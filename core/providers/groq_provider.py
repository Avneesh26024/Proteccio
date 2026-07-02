import os
from groq import Groq
from core.providers.base import LLMProvider

class GroqProvider(LLMProvider):
    """LLM Provider using Groq API for fast inference."""

    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        
        self.client = Groq(api_key=api_key)
        # Using the recommended active replacement model for Llama 3 70B
        self.model = "openai/gpt-oss-120b" 

    def complete(self, prompt: str, text: str) -> str:
        """
        Sends the prompt and text to Groq API.
        If text is empty, just sends the prompt.
        """
        if text:
            full_prompt = f"{prompt}\n\nDocument Text:\n{text}"
        else:
            full_prompt = prompt

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": full_prompt,
                    }
                ],
                model=self.model,
                temperature=0.1,  # Low temperature for compliance tasks
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            return f"API Error: {e}"
