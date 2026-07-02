import os
import yaml
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError
from core.providers.base import LLMProvider

# Load environment variables
load_dotenv()

class GeminiProvider(LLMProvider):
    def __init__(self, config_path="config.yaml"):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing from environment variables. Please set it in your .env file.")
        
        # Using the new google-genai SDK
        self.client = genai.Client(api_key=self.api_key)
        
        # Determine config path
        if not os.path.exists(config_path):
            config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
            
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                self.model_name = config.get("llm_settings", {}).get("model", "gemini-2.0-flash")
        except FileNotFoundError:
            self.model_name = "gemini-2.5-flash-lite"

    def complete(self, prompt: str, text: str) -> str:
        full_prompt = f"{prompt}\n\nText:\n{text}"
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt
            )
            return response.text
        except APIError as e:
            if e.code == 429:
                print("\n[WARNING] Gemini API Quota Exceeded (429). Returning mock response so development is not blocked.")
                return "[MOCK LLM RESPONSE] - Quota exceeded. Please check your Google AI Studio billing/limits."
            return f"API Error: {str(e)}"
        except Exception as e:
            return f"Error during LLM generation: {str(e)}"

# Done condition test
if __name__ == "__main__":
    try:
        print("Initializing GeminiProvider...")
        provider = GeminiProvider()
        print("Sending test request...")
        response = provider.complete("Summarize this text in 2 words", "Hello world, I am testing the API.")
        print("\nResponse:")
        print(response)
    except Exception as e:
        print(f"\nTest failed: {e}")