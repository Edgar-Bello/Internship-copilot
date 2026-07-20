"""Client setup for the school-provided OpenAI API key. Reads the key from .env."""
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

MODEL = "gpt-5.2"

class FitAssessment(BaseModel):
    score: int
    rationale: str
    emphasize: list[str]
    red_flags: list[str]

SCORING_INSTRUCTIONS = """You assess how well a CS student's resume fits an internship posting.
Score 1-5 (5 = exceptional fit). You see only posting METADATA (title, company,
locations, sponsorship) — there is NO job description, so do not invent one.
Base the score only on what is provided. In `emphasize`, name 2-4 items from
the RESUME this posting most wants to hear about. In `red_flags`, list only
constraints visible in the metadata (e.g. no-sponsorship); empty list if none."""

def get_client() -> OpenAI:
    load_dotenv()  # copies .env entries into environment variables
    return OpenAI()  # reads OPENAI_API_KEY from the environment

def score_posting(client: OpenAI, resume: str, posting) -> FitAssessment:
    posting_text = (
        f"Title: {posting['title']}\nCompany: {posting['company']}\n"
        f"Locations: {posting['locations']}\nSponsorship: {posting['sponsorship']}"
    )
    response = client.responses.parse(
        model=MODEL,
        input=[
            {"role": "system", "content": SCORING_INSTRUCTIONS},
            {"role": "user", "content": f"RESUME:\n{resume}\n\nPOSTING:\n{posting_text}"},
        ],
        text_format=FitAssessment,
    )
    assessment = response.output_parsed
    if assessment is None:
        # Narrow the SDK's "maybe" at the boundary - same job raise_for_status does.
        raise RuntimeError(f"model returned no parsed output for: {posting['title']}")
    return assessment

if __name__ == "__main__":
    client = get_client()
    response = client.responses.create(
        model = MODEL,
        input = "Reply with exactly: copilot smoke test OK",
    )
    print(response.output_text)