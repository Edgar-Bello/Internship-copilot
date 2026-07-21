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

DRAFT_INSTRUCTIONS = """You draft a cover letter for a CS student applying to a tech internship.

HARD CONSTRAINTS - a violation makes the draft unusable:
- Every factual claim about the candidate must come from the RESUME. Invent no
  experience, skill, coursework that is not written there.
- You know ONLY the posting metadata (title, company, location, sponsorship).
  There is NO job description. Do not invent the company's products, tech stack,
  culture, team structure, or the role's responsibilities. Where specifics are
  unknown, write generally rather than guessing.
- No placeholder brackets, no invented names, no invented dates.

STYLE: 250-320 words of plain prose, opening with "Dear Hiring Manager," and no
markdown headings. Open with the specific reason this candidate fits this role,
spend the middle on concrete evidence from the resume, close with a direct ask.

The EMPHASIS list comes from a prior fit analysis: lead with those points."""

# Appended only when we actually fetched the employer's own description.
WITH_DESCRIPTION = """
A DESCRIPTION section follows: it is the employer's real posting text. Include one
paragraph on why this specific role and team fit the candidate, drawing ONLY on
facts stated in that DESCRIPTION. Quote no more than a few words at a time."""

# Appended when we could not get a description - the gap must stay visible.
WITHOUT_DESCRIPTION = """
There is NO description available. Write NO paragraph about why this company or
team specifically - you would have to invent it. Stay entirely on the candidate's
evidence and the role title. The human will add that paragraph after reading the
posting themselves."""


def draft_cover_letter(
    client: OpenAI, resume: str, posting, emphasize: list[str], description: str | None = None
) -> str:
    """Return cover letter prose. Plain text, not structured: a letter has no fields."""
    posting_text = (
        f"Title: {posting['title']}\nCompany: {posting['company']}\n"
        f"Locations: {posting['locations']}\nSponsorship: {posting['sponsorship']}"
    )
    emphasis_text = "\n".join(f"- {item}" for item in emphasize) or "- (none recorded)"
    user_content = f"RESUME:\n{resume}\n\nPOSTING:\n{posting_text}\n\nEMPHASIS:\n{emphasis_text}"
    if description:
        instructions = DRAFT_INSTRUCTIONS + WITH_DESCRIPTION
        user_content += f"\n\nDESCRIPTION:\n{description}"
    else:
        instructions = DRAFT_INSTRUCTIONS + WITHOUT_DESCRIPTION
    response = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_content},
        ],
    )
    return response.output_text


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