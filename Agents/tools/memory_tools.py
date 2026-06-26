from google.adk.tools import ToolContext


def save_student_profile(
    grade_level: str,
    gpa_unweighted: float,
    sat_total: int,
    act_composite: int,
    intended_major: str,
    extracurriculars: str,
    awards_and_honors: str,
    career_goals: str,
    annual_budget_usd: int,
    state_of_residence: str,
    school_size_preference: str,
    tool_context: ToolContext,
) -> dict:
    """Save the student's complete academic profile to session memory.

    Args:
        grade_level: Current grade or status (e.g. '9th', '10th', '11th', '12th', 'gap year', 'transfer')
        gpa_unweighted: Unweighted GPA on a 4.0 scale
        sat_total: SAT total score (400-1600), use 0 if not taken
        act_composite: ACT composite score (1-36), use 0 if not taken
        intended_major: Primary field of study the student wants to pursue
        extracurriculars: Comma-separated list of clubs, sports, jobs, volunteering
        awards_and_honors: Comma-separated notable awards, AP scores, honors
        career_goals: Student's long-term career aspirations
        annual_budget_usd: Max annual out-of-pocket cost the family can afford
        state_of_residence: Student's home state (affects in-state tuition eligibility)
        school_size_preference: Preferred school size (small/medium/large/no preference)
    """
    profile = {
        "grade_level": grade_level,
        "gpa_unweighted": gpa_unweighted,
        "sat_total": sat_total,
        "act_composite": act_composite,
        "intended_major": intended_major,
        "extracurriculars": extracurriculars,
        "awards_and_honors": awards_and_honors,
        "career_goals": career_goals,
        "annual_budget_usd": annual_budget_usd,
        "state_of_residence": state_of_residence,
        "school_size_preference": school_size_preference,
    }
    tool_context.state["student_profile"] = profile
    return {"status": "saved", "profile": profile}


def get_student_profile(tool_context: ToolContext) -> dict:
    """Retrieve the student's saved academic profile from session memory."""
    profile = tool_context.state.get("student_profile", {})
    if not profile:
        return {
            "status": "no_profile",
            "message": "No profile saved yet. Ask the student for their academic information.",
        }
    return {"status": "found", "profile": profile}


def update_profile_field(field: str, value: str, tool_context: ToolContext) -> dict:
    """Update a single field in the student's saved profile.

    Args:
        field: The profile field to update (e.g. 'gpa_unweighted', 'sat_total')
        value: The new value for the field
    """
    profile = tool_context.state.get("student_profile", {})
    profile[field] = value
    tool_context.state["student_profile"] = profile
    return {"status": "updated", "field": field, "new_value": value}


def add_school_to_list(
    school_name: str,
    classification: str,
    explanation: str,
    estimated_net_cost_usd: int,
    tool_context: ToolContext,
) -> dict:
    """Add or update a school on the student's tracked college list.

    Args:
        school_name: Full official name of the college/university
        classification: Must be one of: 'reach', 'target', or 'safety'
        explanation: Specific reason for this classification based on student stats
        estimated_net_cost_usd: Estimated annual cost after typical financial aid
    """
    school_list = tool_context.state.get("school_list", [])
    school_list = [s for s in school_list if s["name"].lower() != school_name.lower()]
    school_list.append(
        {
            "name": school_name,
            "classification": classification,
            "explanation": explanation,
            "estimated_net_cost_usd": estimated_net_cost_usd,
        }
    )
    tool_context.state["school_list"] = school_list
    return {"status": "added", "school_list": school_list}


def get_school_list(tool_context: ToolContext) -> dict:
    """Retrieve the student's current tracked school list with reach/target/safety breakdown."""
    school_list = tool_context.state.get("school_list", [])
    return {
        "school_list": school_list,
        "summary": {
            "reach": [s["name"] for s in school_list if s["classification"] == "reach"],
            "target": [s["name"] for s in school_list if s["classification"] == "target"],
            "safety": [s["name"] for s in school_list if s["classification"] == "safety"],
        },
    }


def remove_school_from_list(school_name: str, tool_context: ToolContext) -> dict:
    """Remove a school from the student's tracked list.

    Args:
        school_name: Full name of the school to remove
    """
    school_list = tool_context.state.get("school_list", [])
    school_list = [s for s in school_list if s["name"].lower() != school_name.lower()]
    tool_context.state["school_list"] = school_list
    return {"status": "removed", "school_list": school_list}
