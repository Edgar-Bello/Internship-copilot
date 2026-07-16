import requests

LISTINGS_URL = "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/.github/scripts/listings.json"

def fetch_listings() -> list[dict]:
    resp = requests.get(LISTINGS_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()

def summer_postings(postings: list[dict]) -> list[dict]:
    result = []
    for posting in postings:
        if posting["season"] == "Summer" and posting["active"] and posting["is_visible"]:
            result.append(posting)
    return result

if __name__ == "__main__":
    listings = fetch_listings()
    summer_listings = summer_postings(listings)
    for post in summer_listings:
        print(post["company_name"], post["title"], post["locations"][0])
    print(f"Total Summer Postings: {len(summer_listings)}")