"""Scenario library loader.

Each scenario is a JSON file in scenarios/ describing a patient persona to
role-play against the agent under test.  A scenario file doubles as a
make_call --lead-file payload — its fields flow through the lead-context path
into the persona prompt (see telephony/routes.py and voice_agent/agent_config.py)
— and the runner iterates load_scenarios() to drive coverage.

Schema (see scenarios/*.json):
  scenario_id        short stable id; keys all artifacts as <scenario_id>__<call_sid>
  persona            who the caller is (name, DOB, temperament)
  goal               what they're trying to accomplish on the call
  opening_line       the caller's intended opening, spoken on their turn after
                     the agent greets (woven into the prompt, not a hard greeting)
  pressure           a twist on the call: none | ambiguous_date | interruption |
                     out_of_scope | background_noise | impatient
  expected_behavior  what a CORRECT agent should do — fuel for the judge pass
"""
import json
import os
from glob import glob

SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), "scenarios")

REQUIRED_FIELDS = ("scenario_id", "persona", "goal", "opening_line")
VALID_PRESSURES = {
    "none", "ambiguous_date", "interruption",
    "out_of_scope", "background_noise", "impatient",
}


def load_scenarios(scenarios_dir: str = SCENARIOS_DIR) -> list[dict]:
    """Load and validate every scenario JSON file, sorted by scenario_id."""
    scenarios = []
    for path in sorted(glob(os.path.join(scenarios_dir, "*.json"))):
        with open(path) as f:
            scenario = json.load(f)
        missing = [k for k in REQUIRED_FIELDS if not scenario.get(k)]
        if missing:
            raise ValueError(f"{path}: missing required field(s): {', '.join(missing)}")
        pressure = scenario.get("pressure", "none")
        if pressure not in VALID_PRESSURES:
            raise ValueError(f"{path}: invalid pressure '{pressure}' (expected one of {sorted(VALID_PRESSURES)})")
        scenarios.append(scenario)
    return scenarios


def get_scenario(scenario_id: str, scenarios_dir: str = SCENARIOS_DIR) -> dict:
    """Return a single scenario by its scenario_id."""
    for s in load_scenarios(scenarios_dir):
        if s["scenario_id"] == scenario_id:
            return s
    raise KeyError(f"No scenario with id '{scenario_id}'")


if __name__ == "__main__":
    # Quick sanity view: list the library.
    for s in load_scenarios():
        print(f"{s['scenario_id']:24}  pressure={s.get('pressure', 'none'):16}  {s['goal']}")
