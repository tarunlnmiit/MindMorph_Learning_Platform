"""The Market summary now samples every posting the scraper fetched, not just jobs[0].

Two things have to hold for the frequency claim it makes to be worth anything: the counts must be
exact (they are computed in Python precisely so the model cannot miscount them), and the sample
must actually be the whole fetch rather than one posting wearing a denominator.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.market.market_agent import MarketAnalysisAgent


def _agent():
    """An agent without __init__ — no scraper, no real model, just the prompt-building code."""
    agent = MarketAnalysisAgent.__new__(MarketAnalysisAgent)
    agent.llm = MagicMock()
    agent.llm.ainvoke = AsyncMock(return_value=MagicMock(content="SUMMARY"))
    return agent


def _posting(*skills):
    return {"title": "ML Engineer", "ai_key_skills": list(skills)}


def test_frequency_table_counts_every_posting_and_keeps_the_denominator():
    jobs = [_posting("Python", "PyTorch"), _posting("Python", "SQL"), _posting("Python")]

    table = MarketAnalysisAgent._frequency_table(jobs)

    assert "Python - 3/3 postings" in table
    # Named once, so it is below the ranking threshold — counted, not silently dropped.
    assert "PyTorch" not in table
    assert "2 further skills are named by exactly 1/3 postings" in table


async def test_summary_prompt_carries_all_postings_not_just_the_first():
    agent = _agent()
    jobs = [_posting("Python"), _posting("Python", "Kubernetes"), _posting("Kubernetes")]

    assert await agent.summarize_job(jobs) == "SUMMARY"

    prompt = agent.llm.ainvoke.await_args.args[0]
    assert "Posting 3 of 3" in prompt
    assert "Kubernetes - 2/3 postings" in prompt


async def test_a_single_posting_dict_still_works_and_says_so():
    agent = _agent()

    assert await agent.summarize_job(_posting("Python")) == "SUMMARY"

    prompt = agent.llm.ainvoke.await_args.args[0]
    assert "1 job postings were sampled" in prompt
    # One posting cannot support a frequency claim, and the table says that rather than
    # reporting "Python - 1/1 postings" as if it were evidence of demand.
    assert "No skill is named by more than one posting." in prompt


async def test_sample_is_capped_so_a_larger_fetch_cannot_blow_the_token_budget():
    agent = _agent()

    await agent.summarize_job([_posting("Python") for _ in range(25)])

    prompt = agent.llm.ainvoke.await_args.args[0]
    assert f"{MarketAnalysisAgent.MAX_POSTINGS} job postings were sampled" in prompt
    assert f"Posting {MarketAnalysisAgent.MAX_POSTINGS + 1} of" not in prompt


def test_salary_reads_the_keys_the_actor_actually_returns():
    # ai_salary_minvalue (no underscores) matched nothing, so every posting read "not stated".
    job = {
        "ai_salary_min_value": 150000,
        "ai_salary_max_value": 200000,
        "ai_salary_currency": "USD",
        "ai_salary_unit_text": "YEAR",
    }

    assert MarketAnalysisAgent._salary_line(job) == "150,000 - 200,000 USD per YEAR"
    assert MarketAnalysisAgent._salary_line({}) == "not stated"
