"""Client setup for the school-provided OpenAI API key. Reads the key from .env."""
from dotenv import load_dotenv
from openai import OpenAI

MODEL = "gpt-5.2"

def get_client() -> OpenAI:
    load_dotenv()  # copies .env entries into environment variables
    return OpenAI()  # reads OPENAI_API_KEY from the environment

if __name__ == "__main__":
    client = get_client()
    response = client.responses.create(
        model = MODEL,
        input = "Reply with exactly: copilot smoke test OK",
    )
    print(response.output_text)