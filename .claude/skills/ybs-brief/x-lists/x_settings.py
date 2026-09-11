#!/usr/bin/env python3
"""x_settings.py - the one place that reads the X half of settings.md.

The root `settings.md` holds both halves of the morning run. Every number the
X pipeline obeys lives in its `## X numbers` and `## X fixed` tables, and the
model/effort for each agent step in its `## X models` tables. The article
brief's own `## Numbers` and `## Models` are skipped here, which is why both
halves may name a step `cluster` without clashing. Nothing here guesses a
default number; a missing table or a duplicate key is a hard error, not a
fallback.

Usage as a library:

    from x_settings import load_settings
    settings = load_settings()                       # <root>/settings.md
    settings = load_settings(Path("/other/settings.md"))

    settings["x_window_hours"]      -> int
    settings["x_velocity_percentile"] -> int (a "90%" cell becomes int 90)
    settings["cluster_model"]       -> str   (from the Models table)
    settings["cluster_effort"]      -> str

Usage from the command line (mirrors ybs_run.py's `settings` subcommand):

    python3 x_settings.py            # print every key=value, one per line
    python3 x_settings.py x_picks_max  # print just that one value

Python 3, standard library only.
"""

import re
import sys
from pathlib import Path


def die(msg: str, code: int = 2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def project_root() -> Path:
    """<root>/.claude/skills/ybs-brief/x-lists/x_settings.py -> <root>"""
    return Path(__file__).resolve().parents[4]


def default_settings_path() -> Path:
    """<root>/settings.md, four folders up from x-lists/."""
    return project_root() / "settings.md"


def _parse_value(raw: str):
    raw = raw.strip()
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+%", raw):
        return int(raw[:-1])
    if '"' in raw:
        found = re.findall(r'"([^"]*)"', raw)
        if found:
            return found
    return raw


def load_settings(path: Path = None) -> dict:
    """Read settings.md's `## X numbers`, `## X fixed` and `## X models`.

    - `## X numbers` and `## X fixed`: `| key | value | meaning |` -> out[key].
      A run of digits becomes an int, `NN%` becomes the int NN, a
      comma-separated `"a", "b"` cell becomes a list of strings, anything
      else is kept as the text in the cell.
    - `## X models`: `| step | model | effort | why |` -> two keys per row,
      `<step>_model` and `<step>_effort`. Every model row must carry an
      effort; a step with no model column is left out, not defaulted.

    Dies (exit 2) on: no file, an unreadable file, a key named twice
    anywhere in the document, or a Models row with no effort.
    """
    path = path or default_settings_path()
    path = Path(path)
    if not path.exists():
        die(f"no settings file at {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        die(f"cannot read {path}: {e}")

    out: dict = {}
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        key, raw = cells[0], cells[1]
        if not key or key.lower() in ("setting", "step", "agent") or set(key) <= set("-: "):
            continue

        if section == "x models":
            if len(cells) < 3 or not cells[2]:
                die(f"settings.md: model row '{key}' has no effort")
            # The whole first cell is the step's name, verbatim commas and
            # all (e.g. "build filter, score, run-chain", "verify, check 6")
            # -- it names one row of the table, not a list to split apart.
            skey = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
            for suffix, value in (("_model", cells[1]), ("_effort", cells[2])):
                field = skey + suffix
                if field in out:
                    die(f"settings.md names {field} twice")
                out[field] = value
            continue

        if section in ("x numbers", "x fixed"):
            if key in out:
                die(f"settings.md names {key} twice")
            out[key] = _parse_value(raw)

    if not out:
        die(f"{path} holds no settings")
    return out


def default_sources_path() -> Path:
    """<root>/sources.md, where the X lists are listed."""
    return project_root() / "sources.md"


def read_x_lists(path: Path = None) -> list:
    """The `## X lists` section of sources.md -> [{name, slug, url}].

    One line each: `1. Name - https://x.com/i/lists/...`. The marker and its
    number are decoration. Lines under any other heading are news front pages
    and belong to the article half, which reads them with its own parser in
    ybs_run.py -- the two halves parse the same file shape on purpose, so
    neither has to import the other.

    Dies if the file is missing or the section names no list: the X half with
    nothing to read is a mistake, not an empty run.
    """
    path = Path(path) if path else default_sources_path()
    if not path.exists():
        die(f"no sources file at {path}")
    rows, section = [], ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("    ") or line.startswith("\t"):
            continue
        if line.strip().startswith("#"):
            section = line.strip().lstrip("#").strip().lower()
            continue
        if section != "x lists":
            continue
        stripped = re.sub(r"^\s*(\d+[.)]|[-*+])\s+", "", line.strip())
        if not stripped or "http" not in stripped:
            continue
        parts = [p.strip() for p in re.split(r"\s+[-\u2013\u2014]\s+", stripped) if p.strip()]
        url = next((p for p in parts if p.startswith("http")), None)
        if not url or parts[0] == url:
            continue
        name = " - ".join(parts[:parts.index(url)])
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "list"
        rows.append({"name": name, "slug": slug, "url": url})
    if not rows:
        die(f"{path} has no `## X lists` section, or it names no list")
    seen = set()
    for r in rows:
        if r["url"] in seen:
            die(f"sources.md names the same X list twice: {r['url']}")
        seen.add(r["url"])
    return rows


def require(settings: dict, *keys):
    """Fetch several keys at once, dying with all missing names at once."""
    missing = [k for k in keys if k not in settings]
    if missing:
        die("settings.md is missing: " + ", ".join(missing))
    return tuple(settings[k] for k in keys)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    settings = load_settings()
    if argv:
        for key in argv:
            if key not in settings:
                die(f"no such setting: {key}")
            print(settings[key])
    else:
        for key in sorted(settings):
            print(f"{key}={settings[key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
