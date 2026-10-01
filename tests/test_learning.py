from discovery.agent import DiscoveryAgent
from discovery.agents.experiment import design
from discovery.agents.learning import NEW_EXPERIMENT, advise
from discovery.models import ExperimentLearning
from discovery.paths import sample_dir

PAST = ExperimentLearning(
    opportunity_id="opp-recommendations",
    opportunity="AI recommendations",
    hypothesis="Users want AI recommendations.",
    experiment="Users clicked AI recommendations.",
    result="Clicks increased.",
    learning="Clicks were high but follow-through was low.",
    decision="Iterate",
)


def test_clicks_without_follow_through_change_the_next_experiment():
    assert advise(PAST) == (
        "Test actionable recommendations instead of informational recommendations."
    )


def test_the_designer_reads_that_learning_and_leaves_other_opportunities_alone(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    current = agent.opportunity("opp-instrumentation")
    assert current is not None
    recommendations = current.model_copy(
        update={
            "id": "opp-recommendations",
            "theme": "recommendations",
            "title": "AI recommendations",
            "problem": "Users ignore recommendations that only explain the data.",
        }
    )
    plan = design(recommendations, agent.memory().records, [PAST])
    assert "Past experiment: Users clicked AI recommendations." in plan.stages[1].lines
    assert "Past learning: Clicks were high but follow-through was low." in plan.stages[1].lines
    assert f"New experiment: {NEW_EXPERIMENT}" in plan.stages[1].lines
    assert plan.informed_experiment == NEW_EXPERIMENT
    assert plan.selected == "Selected: C + targeted interviews."

    untouched = design(current, agent.memory().records, [PAST])
    assert untouched.informed_experiment == ""
    assert all("actionable recommendations" not in line for line in untouched.stages[1].lines)

    agent.remember_learning(PAST)
    stored = agent.experiment_learnings()
    assert stored[0].experiment == "Users clicked AI recommendations."
    assert stored[0].learning == "Clicks were high but follow-through was low."

    remembered = agent.experiment("opp-instrumentation")
    assert remembered is not None and remembered.memory_chain is not None
    chain = remembered.memory_chain
    assert chain.opportunity == "Guided tracking plans"
    assert chain.hypothesis == "Users want guided tracking plans."
    assert chain.experiment == "Guided tracking plans fake door"
    assert chain.result == "No result is recorded."
    assert chain.learning == "No learning is recorded yet."
    assert chain.decision == "Waiting for a result"
    assert remembered.informed_experiment == ""
