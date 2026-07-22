"""Guards on what the tool is allowed to type into a real job application.

Every case here comes from a decision we made deliberately, so if someone later
loosens a rule these fail and say which promise broke.
"""
from copilot.applying import FILL_RULES, NEVER_FILL, _is_self_id, _normalize, _value_for

# Labels copied verbatim from Anduril's live Greenhouse form.
LEGAL_DECLARATIONS = [
    "U.S. WORK AUTHORIZATION*",
    "Will you require sponsorship from Anduril for employment now or in the future (e.g, H1B visa)?*",
    "EXPORT CONTROLS - This position requires access to information and technology that is "
    "subject to U.S. export controls.*",
    "Will you be returning to school at the end of the internship to continue academic studies "
    "for at least one quarter/semester*",
    "Are you willing to work in-person for 12 weeks during the internship? *",
    "How did you hear about Anduril?*",
]

SELF_ID_LABELS = ["Gender", "Are you Hispanic/Latino?", "Veteran Status", "Disability Status"]

FULL_IDENTITY = {
    "personal": {"first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com",
                 "phone": "555-0000", "country": "United States"},
    "links": {"linkedin": "https://linkedin.com/in/ada", "github": "https://github.com/ada",
              "website": ""},
    "education": {"school": "Example State", "degree": "Bachelor's Degree",
                  "major": "Computer Science", "graduation_month": "May",
                  "graduation_year": "2028"},
    "self_identification": {"gender": "Male", "hispanic_latino": "Yes",
                            "veteran_status": "I am not a protected veteran",
                            "disability_status": "No"},
}


class TestLegalDeclarationsStayManual:
    """These invert between employers, so one stored answer cannot serve both."""

    def test_never_answered_even_with_a_full_identity(self):
        for label in LEGAL_DECLARATIONS:
            assert _value_for(label, FULL_IDENTITY) is None, label

    def test_no_fill_rule_can_ever_reach_them(self):
        # A new FILL_RULES entry like ("work", ...) must not start answering
        # "U.S. WORK AUTHORIZATION". NEVER_FILL is checked first, and this proves it.
        loosened = FULL_IDENTITY | {"personal": FULL_IDENTITY["personal"] | {"country": "Yes"}}
        for label in LEGAL_DECLARATIONS:
            assert _value_for(label, loosened) is None, label

    def test_the_banned_list_is_matched_case_insensitively(self):
        assert _value_for("U.S. Work Authorization", FULL_IDENTITY) is None
        assert _value_for("SPONSORSHIP REQUIRED?", FULL_IDENTITY) is None


class TestSelfIdentificationIsOptIn:
    def test_blank_config_leaves_every_question_to_the_human(self):
        blank = FULL_IDENTITY | {"self_identification": {
            "gender": "", "hispanic_latino": "", "veteran_status": "", "disability_status": "",
        }}
        for label in SELF_ID_LABELS:
            assert _value_for(label, blank) is None, label

    def test_absent_section_is_not_an_error(self):
        without = {k: v for k, v in FULL_IDENTITY.items() if k != "self_identification"}
        for label in SELF_ID_LABELS:
            assert _value_for(label, without) is None, label

    def test_declared_values_are_used_verbatim(self):
        assert _value_for("Gender", FULL_IDENTITY) == "Male"
        assert _value_for("Veteran Status", FULL_IDENTITY) == "I am not a protected veteran"

    def test_the_model_is_never_offered_these_fields(self):
        # prefill() withholds the client when this returns True; that is the only
        # thing keeping demographic answers on exact matching.
        for label in SELF_ID_LABELS:
            assert _is_self_id(label) is True, label
        assert _is_self_id("School*") is False
        assert _is_self_id("Degree*") is False


class TestOrdinaryFieldsStillFill:
    def test_form_labels_map_to_identity_values(self):
        assert _value_for("First Name*", FULL_IDENTITY) == "Ada"
        assert _value_for("Email*", FULL_IDENTITY) == "ada@example.com"
        assert _value_for("School*", FULL_IDENTITY) == "Example State"
        assert _value_for("End date year*", FULL_IDENTITY) == "2028"
        assert _value_for("LinkedIn Profile", FULL_IDENTITY) == "https://linkedin.com/in/ada"

    def test_first_name_wins_over_the_looser_name_rule(self):
        # FILL_RULES is ordered; "last name" must not be caught by "first name".
        assert _value_for("Last Name*", FULL_IDENTITY) == "Lovelace"

    def test_empty_config_value_means_leave_it_alone(self):
        assert _value_for("Website", FULL_IDENTITY) is None

    def test_unknown_labels_are_left_alone(self):
        assert _value_for("What is your top location preference? *", FULL_IDENTITY) is None
        assert _value_for("Preferred pronouns", FULL_IDENTITY) is None


class TestNormalize:
    """How option text is compared. Each case is a real difference we hit."""

    def test_a_leading_article_is_noise(self):
        assert _normalize("The University of Texas Rio Grande Valley") == \
               _normalize("University of Texas Rio Grande Valley")

    def test_case_and_punctuation_are_noise(self):
        assert _normalize("Bachelor's Degree") == _normalize("BACHELORS DEGREE")

    def test_different_schools_stay_different(self):
        assert _normalize("University of Texas at Austin") != \
               _normalize("University of Texas Rio Grande Valley")

    def test_different_degree_levels_stay_different(self):
        assert _normalize("Bachelor's Degree") != _normalize("Master's Degree")


def test_rules_are_ordered_longest_first_within_a_prefix():
    # "first name"/"last name" must precede any bare "name" rule someone adds.
    needles = [needle for needle, _ in FILL_RULES]
    assert "name" not in needles, "a bare 'name' rule would swallow first/last name"


def test_never_fill_covers_the_categories_we_promised():
    for term in ("authorization", "sponsorship", "export control", "citizen"):
        assert term in NEVER_FILL
