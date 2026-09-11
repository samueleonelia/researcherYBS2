#!/usr/bin/env python3
"""Tests for x_checks.py's check 10 -- the mechanical slice only (see the
block comment above check10_mechanical in x_checks.py for what is left to
the human/sonnet verifier and why).

x_checks.py must not import x_filter.py; these tests do not either, and
they do not invoke the real `claude` CLI.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import x_checks  # noqa: E402

SETTINGS = {"x_words_per_sentence_max": 30}

PICKS_MD = """# X list picks

Run: 2026-09-06-0954 · subjects judged: 36 · kept: 5 · cut by the ceiling: 8

## 1. US envoys' peace talks in Kyiv

- **Tag:** TRENDING
- **Flags:** VELOCITY
- **Storyline:** Russia grinding down Ukraine while its own state rots
- **Why:** the list is moving fast on it.
- **The tweet that states it best:**
  - @ZelenskyyUa — https://x.com/ZelenskyyUa/status/2096536036985774114
  - > A meeting with our negotiating team ahead of the meeting with envoys.

## 2. Labour's push to sanction Israel

- **Tag:** TRENDING
- **Flags:** CONVERGENCE
- **Storyline:** Israel, antisemitism and the double standard
- **Why:** several list members converged on it.
- **The tweet that states it best:**
  - @GBNEWS — https://x.com/GBNEWS/status/2096500467123581235
  - > Andy Burnham warned Israel sanctions risk British national security

## 3. Florida designates the Muslim Brotherhood and CAIR terror organizations

- **Tag:** CURIOUS
- **Flags:** none
- **Storyline:** Islamic totalitarianism and the refusal to name the enemy
- **Why:** a named state designation.
- **The tweet that states it best:**
  - @AdamMilstein — https://x.com/AdamMilstein/status/2096276673410842984
  - > Florida Gov. DeSantis announces the designation.
"""

BRIEF_OK = """# What the list is moving on

**Run:** 2026-09-06-0954 · **Window:** 1 hours, to 6 September 2026 at 09:54 UTC

## TRENDING

### 1. Zelensky says his team met US envoys in Kyiv.

Zelensky posted that his team met the envoys. He said Ukraine wants the war to end.

This is a first step, not a deal. The post names no terms and no date.

- **Storyline:** Russia grinding down Ukraine while its own state rots
- **Flags:** VELOCITY
- **Source:** [@ZelenskyyUa](https://x.com/ZelenskyyUa/status/2096536036985774114)

### 2. Burnham warns Israel sanctions risk British security.

Burnham made the warning on air. The list converged on it fast.

Prudential arguments are not moral ones. The post names no sanction and no date.

- **Storyline:** Israel, antisemitism and the double standard
- **Flags:** CONVERGENCE
- **Source:** [@GBNEWS](https://x.com/GBNEWS/status/2096500467123581235)

## CURIOUS

### 3. Florida designates the Muslim Brotherhood and CAIR as terror groups.

DeSantis announced the designation. No other list member picked it up.

Naming the enemy matters. The post names no legal instrument or date.

- **Storyline:** Islamic totalitarianism and the refusal to name the enemy
- **Flags:** none
- **Source:** [@AdamMilstein](https://x.com/AdamMilstein/status/2096276673410842984)

---

3 picks from 36 subjects judged. TRENDING items carry a flag from the list. CURIOUS ones carry none.
"""


class TestParsePicksForBrief(unittest.TestCase):
    def test_parses_title_tag_storyline_url_in_order(self):
        picks = x_checks.parse_picks_for_brief(PICKS_MD)
        self.assertEqual(len(picks), 3)
        self.assertEqual(picks[0]["tag"], "TRENDING")
        self.assertEqual(picks[2]["tag"], "CURIOUS")
        self.assertEqual(picks[0]["storyline"], "Russia grinding down Ukraine while its own state rots")
        self.assertEqual(picks[0]["url"], "https://x.com/ZelenskyyUa/status/2096536036985774114")


class TestParseBriefItems(unittest.TestCase):
    def test_tags_each_item_with_its_section(self):
        items = x_checks.parse_brief_items(BRIEF_OK)
        self.assertEqual([it["section"] for it in items], ["TRENDING", "TRENDING", "CURIOUS"])
        self.assertEqual(items[0]["url"], "https://x.com/ZelenskyyUa/status/2096536036985774114")


class TestExtractProseSentences(unittest.TestCase):
    def test_excludes_bullets_and_metadata_lines(self):
        sentences = x_checks.extract_prose_sentences(BRIEF_OK)
        joined = " ".join(sentences)
        self.assertNotIn("Storyline:", joined)
        self.assertNotIn("Flags:", joined)
        self.assertNotIn("Source:", joined)
        self.assertNotIn("**Run:**", joined)

    def test_includes_headings_and_closing_line(self):
        sentences = x_checks.extract_prose_sentences(BRIEF_OK)
        self.assertTrue(any("Zelensky says his team met US envoys in Kyiv" in s for s in sentences))
        self.assertTrue(any("TRENDING items carry a flag from the list" in s for s in sentences))


class TestCheck10Mechanical(unittest.TestCase):
    def test_passes_on_a_correct_brief(self):
        ok, reason = x_checks.check10_mechanical(PICKS_MD, BRIEF_OK, SETTINGS)
        self.assertTrue(ok, reason)

    def test_fails_when_brief_is_empty(self):
        ok, reason = x_checks.check10_mechanical(PICKS_MD, "", SETTINGS)
        self.assertFalse(ok)
        self.assertIn("empty", reason)

    def test_fails_when_brief_is_missing_a_pick(self):
        brief_missing = BRIEF_OK.split("## CURIOUS")[0] + (
            "\n---\n\n2 picks from 36 subjects judged. "
            "TRENDING items carry a flag from the list. CURIOUS ones carry none.\n"
        )
        ok, reason = x_checks.check10_mechanical(PICKS_MD, brief_missing, SETTINGS)
        self.assertFalse(ok)
        self.assertIn("3", reason)  # picks.md has 3 picks, brief has 2 items

    def test_fails_when_brief_has_an_extra_permalink_not_in_picks(self):
        brief_extra = BRIEF_OK.replace(
            "[@AdamMilstein](https://x.com/AdamMilstein/status/2096276673410842984)",
            "[@someoneelse](https://x.com/someoneelse/status/9999999999999999999)",
        )
        ok, reason = x_checks.check10_mechanical(PICKS_MD, brief_extra, SETTINGS)
        self.assertFalse(ok)

    def test_fails_when_curious_precedes_trending(self):
        swapped = BRIEF_OK.replace("## TRENDING", "## __T__").replace(
            "## CURIOUS", "## TRENDING").replace("## __T__", "## CURIOUS")
        ok, reason = x_checks.check10_mechanical(PICKS_MD, swapped, SETTINGS)
        self.assertFalse(ok)
        self.assertIn("CURIOUS", reason)

    def test_fails_on_a_sentence_over_the_word_ceiling(self):
        long_brief = BRIEF_OK.replace(
            "Zelensky posted that his team met the envoys.",
            "Zelensky posted that his team met the envoys after a very long series of "
            "discussions that dragged on for hours and covered many many many many many "
            "many many many many many many many topics of importance to everyone.",
        )
        ok, reason = x_checks.check10_mechanical(PICKS_MD, long_brief, SETTINGS)
        self.assertFalse(ok)
        self.assertIn("words", reason)

    def test_fails_when_a_storyline_does_not_appear_in_the_brief(self):
        altered = BRIEF_OK.replace(
            "Russia grinding down Ukraine while its own state rots",
            "Russia grinding down Ukraine",
        )
        ok, reason = x_checks.check10_mechanical(PICKS_MD, altered, SETTINGS)
        self.assertFalse(ok)
        self.assertIn("storyline", reason)

    def test_fails_when_settings_has_no_ceiling(self):
        ok, reason = x_checks.check10_mechanical(PICKS_MD, BRIEF_OK, {})
        self.assertFalse(ok)
        self.assertIn("x_words_per_sentence_max", reason)

    def test_fails_when_an_item_is_filed_under_the_wrong_section(self):
        # Pick #2 is TRENDING in picks.md; file its item under CURIOUS in
        # the brief instead, leaving everything else the same shape.
        wrong_section = """# What the list is moving on

**Run:** 2026-09-06-0954 · **Window:** 1 hours, to 6 September 2026 at 09:54 UTC

## TRENDING

### 1. Zelensky says his team met US envoys in Kyiv.

Zelensky posted that his team met the envoys.

This is a first step, not a deal.

- **Storyline:** Russia grinding down Ukraine while its own state rots
- **Flags:** VELOCITY
- **Source:** [@ZelenskyyUa](https://x.com/ZelenskyyUa/status/2096536036985774114)

## CURIOUS

### 2. Burnham warns Israel sanctions risk British security.

Burnham made the warning on air.

Prudential arguments are not moral ones.

- **Storyline:** Israel, antisemitism and the double standard
- **Flags:** CONVERGENCE
- **Source:** [@GBNEWS](https://x.com/GBNEWS/status/2096500467123581235)

### 3. Florida designates the Muslim Brotherhood and CAIR as terror groups.

DeSantis announced the designation.

Naming the enemy matters.

- **Storyline:** Islamic totalitarianism and the refusal to name the enemy
- **Flags:** none
- **Source:** [@AdamMilstein](https://x.com/AdamMilstein/status/2096276673410842984)

---

3 picks from 36 subjects judged. TRENDING items carry a flag from the list. CURIOUS ones carry none.
"""
        ok, reason = x_checks.check10_mechanical(PICKS_MD, wrong_section, SETTINGS)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
