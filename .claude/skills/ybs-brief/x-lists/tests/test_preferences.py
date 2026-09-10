#!/usr/bin/env python3
"""preferences.md is read by two pipelines that share no code. This pins the
two readers to the same rule, so a note Yaron writes to himself never reaches
one pipeline's prompts and not the other's."""

import importlib.util
import inspect
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
import x_run  # noqa: E402

ROOT = HERE.parents[5]
spec = importlib.util.spec_from_file_location(
    "ybs_run", ROOT / ".claude" / "skills" / "ybs-brief" / "scripts" / "ybs_run.py")
ybs_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ybs_run)

SAMPLE = """# The note
Never lead with a celebrity story.

- I don't use the crime ones.

---
# a note
Keep the leads shorter.

I don't use the crime ones.
<!-- one more note --> More energy policy.
"""
WANT = ["Keep the leads shorter.", "I don't use the crime ones.", "More energy policy."]


class TestPreferenceReaders(unittest.TestCase):
    def test_same_code_in_both_pipelines(self):
        self.assertEqual(inspect.getsource(x_run.preference_lines),
                         inspect.getsource(ybs_run.preference_lines))

    def test_notes_never_reach_a_prompt(self):
        self.assertEqual(x_run.preference_lines(SAMPLE), WANT)
        self.assertEqual(ybs_run.preference_lines(SAMPLE), WANT)

    def test_a_file_with_no_rule_is_read_whole(self):
        self.assertEqual(x_run.preference_lines("Keep it short.\n# note\n"), ["Keep it short."])
        self.assertEqual(x_run.preference_lines("---\nKeep it short.\n"), ["Keep it short."])

    def test_the_real_file_holds_no_hidden_instruction(self):
        text = (ROOT / "preferences.md").read_text(encoding="utf-8")
        lines = x_run.preference_lines(text)
        for example in ("celebrity", "crime", "energy", "shorter"):
            self.assertFalse(any(example in ln for ln in lines),
                             f"the help block leaks '{example}' as an instruction: {lines}")

    def test_x_empty_note(self):
        self.assertEqual(x_run.read_preferences(ROOT / "preferences.md", "(none)"), "(none)")
        self.assertEqual(x_run.read_preferences(ROOT / "no-such-file.md", "(none)"), "(none)")


if __name__ == "__main__":
    unittest.main()
