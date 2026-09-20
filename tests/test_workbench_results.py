"""Verification summaries must reflect coverage as well as detected failures."""

import pytest

from cad_integrity.workbench_results import (
    CheckResult,
    CheckState,
    Completion,
    DecisionBrief,
    verification_markdown,
    verification_summary,
    with_outcome_details,
)


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        ((), "Not verified"),
        ((CheckState.NOT_RUN,), "Not verified"),
        ((CheckState.NOT_APPLICABLE,), "Not verified"),
        ((CheckState.PASSED, CheckState.NOT_RUN), "Not verified"),
        ((CheckState.NOT_APPLICABLE, CheckState.NOT_RUN), "Not verified"),
        ((CheckState.FAILED,), "Needs review"),
        ((CheckState.FAILED, CheckState.UNAVAILABLE, CheckState.NOT_RUN), "Needs review"),
        ((CheckState.UNAVAILABLE, CheckState.NOT_RUN), "Unavailable"),
        ((CheckState.PASSED, CheckState.UNAVAILABLE), "Unavailable"),
        ((CheckState.PASSED, CheckState.PASSED), "Passed"),
        ((CheckState.PASSED, CheckState.NOT_APPLICABLE), "Passed"),
    ],
)
def test_verification_summary_and_retained_projection(states, expected):
    checks = tuple(CheckResult(f"Check {i}", state) for i, state in enumerate(states))

    assert verification_summary(checks) == expected
    ledger = verification_markdown(checks)
    assert ledger.splitlines()[1] == f"Verification: {expected}"
    brief = with_outcome_details(
        DecisionBrief("Analysis completed", False, "## Decision"),
        completion=Completion.COMPLETED,
        checks=checks,
    )
    assert ledger in brief.markdown
    for check in checks:
        assert f"- {check.name} [{check.status.value}]" in ledger
