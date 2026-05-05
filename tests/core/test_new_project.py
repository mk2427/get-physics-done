"""Spec-text tests for commit 11: M1.6 knowledge hook + M1.7 assertion hook in new-project.

All tests are spec-text tests — they read the .md source files and assert strings
are present.  No runtime invocation is needed.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SPEC = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "new-project.md"
COMMAND_FILE = REPO_ROOT / "src" / "gpd" / "commands" / "new-project.md"

# Section-heading anchors used to isolate each hook's body from surrounding text.
_M1_6_HEADING = "#### M1.6. Knowledge Stabilization Hook"
_M1_7_HEADING = "#### M1.7. Assertion Promotion Hook"


def _m16_body(workflow_text: str) -> str:
    """Return the workflow text for the M1.6 section only (up to the M1.7 heading)."""
    after_m16 = workflow_text.split(_M1_6_HEADING, 1)[1]
    return after_m16.split(_M1_7_HEADING, 1)[0]


def _m17_body(workflow_text: str) -> str:
    """Return the workflow text for the M1.7 section only (from its heading onward)."""
    return workflow_text.split(_M1_7_HEADING, 1)[1]


def test_hook_prompts_on_yes() -> None:
    """M1.6 and M1.7 both document a 'Y (or Enter)' path that invokes the downstream skill."""
    workflow_text = WORKFLOW_SPEC.read_text(encoding="utf-8")

    # M1.6: Y path invokes digest-knowledge --adversarial
    m16 = _m16_body(workflow_text)
    assert "Y (or Enter)" in m16
    assert "digest-knowledge --adversarial" in m16

    # M1.7: Y path invokes digest-assertion
    m17 = _m17_body(workflow_text)
    assert "Y (or Enter)" in m17
    assert "digest-assertion" in m17


def test_hook_skipped_on_no() -> None:
    """Both M1.6 and M1.7 document an 'n' path that logs 'deferred' and continues."""
    workflow_text = WORKFLOW_SPEC.read_text(encoding="utf-8")

    m16 = _m16_body(workflow_text)
    assert "deferred" in m16
    assert "manually when ready" in m16

    m17 = _m17_body(workflow_text)
    assert "deferred" in m17
    assert "manually when ready" in m17


def test_no_knowledge_hook_flag_bypasses_prompt() -> None:
    """--no-knowledge-hook appears in the command file flags section and the workflow M1.6 section."""
    command_text = COMMAND_FILE.read_text(encoding="utf-8")
    workflow_text = WORKFLOW_SPEC.read_text(encoding="utf-8")

    # Command file must declare the flag
    assert "--no-knowledge-hook" in command_text

    # Workflow M1.6 section must reference the bypass
    m16 = _m16_body(workflow_text)
    assert "--no-knowledge-hook" in m16


def test_no_assertion_hook_flag_bypasses_prompt() -> None:
    """--no-assertion-hook appears in the command file flags section and the workflow M1.7 section."""
    command_text = COMMAND_FILE.read_text(encoding="utf-8")
    workflow_text = WORKFLOW_SPEC.read_text(encoding="utf-8")

    # Command file must declare the flag
    assert "--no-assertion-hook" in command_text

    # Workflow M1.7 section must reference the bypass
    m17 = _m17_body(workflow_text)
    assert "--no-assertion-hook" in m17
