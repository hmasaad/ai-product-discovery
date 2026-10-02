from discovery.agent import DiscoveryAgent
from discovery.agents.value import FORMULA, rank
from discovery.paths import sample_dir


def test_a_cheap_uncertain_experiment_outranks_an_expensive_build():
    values, chain = rank(
        [
            {
                "name": "AI Spending Insight",
                "uncertainty": "High",
                "information": "Medium",
                "impact": "High",
                "cost": "Low",
                "weight": 0.9,
            },
            {
                "name": "Onboarding redesign",
                "uncertainty": "High",
                "information": "Medium",
                "impact": "Medium",
                "cost": "Medium",
                "weight": 0.5,
            },
            {
                "name": "Premium AI Coach",
                "uncertainty": "High",
                "information": "High",
                "impact": "High",
                "cost": "High",
                "weight": 0.8,
            },
            {
                "name": "Notification test",
                "uncertainty": "Low",
                "information": "Low",
                "impact": "Low",
                "cost": "Low",
                "weight": 0.2,
            },
        ]
    )
    assert [(item.name, item.priority, item.prioritize) for item in values] == [
        ("AI Spending Insight", "9", True),
        ("Premium AI Coach", "3", False),
        ("Onboarding redesign", "3", False),
        ("Notification test", "1", False),
    ]
    assert chain == [
        "High uncertainty",
        "High information gain",
        "High decision impact",
        "Low-cost experiment",
        "PRIORITIZE",
    ]
    assert values[0].information_gain == "High"
    assert values[0].decision_impact == "High"
    assert values[0].cost == "Low"
    assert values[3].information_gain == "Low"


def test_northstar_prioritizes_the_highest_impact_low_cost_experiment(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    portfolio = agent.portfolio()
    assert portfolio.formula == FORMULA
    assert portfolio.chain == [
        "High uncertainty",
        "High information gain",
        "High decision impact",
        "Low-cost experiment",
        "PRIORITIZE",
    ]
    assert portfolio.values[0].name == "Guided tracking plans"
    assert portfolio.values[0].priority == "9"
    assert portfolio.values[0].prioritize is True
    by_name = {item.name: item for item in portfolio.values}
    assert by_name["Analysis PMs can run themselves"].priority == "9"
    assert by_name["Analysis PMs can run themselves"].prioritize is False
    assert by_name["Insights that cite our events"].decision_impact == "Medium"
    assert by_name["Dark theme"].decision_impact == "Low"
    assert by_name["Bundled session replay"].decision_impact == "Low"
    assert int(by_name["Dark theme"].priority) < int(portfolio.values[0].priority)
