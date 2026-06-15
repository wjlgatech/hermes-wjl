"""Session search FTS query building.

Regression test: a hyphenated query like "compounding-anything" must not reach
FTS5 as `compounding-anything*` (where `-` is the NOT/column operator, raising
"no such column: anything" and 500-ing the whole search). It must become an AND
of prefix terms (`compounding* anything*`).
"""

import sqlite3

import pytest

from hermes_cli.web_server import _build_fts_prefix_query


@pytest.mark.parametrize(
    "query,expected",
    [
        ("compounding-anything", "compounding* anything*"),
        ("loop engineering", "loop* engineering*"),
        ('"exact phrase"', '"exact phrase"'),  # explicit phrase preserved
        ("already*", "already*"),  # explicit wildcard preserved
        ("v1.2", "v1* 2*"),  # dots split too
        ("Projects/compounding-anything", "Projects* compounding* anything*"),
        ("---", ""),  # pure punctuation -> empty
        ("   ", ""),
    ],
)
def test_build_fts_prefix_query(query, expected):
    assert _build_fts_prefix_query(query) == expected


def _fts_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE m USING fts5(content)")
    conn.execute("INSERT INTO m(content) VALUES (?)", ("we discussed compounding anything strategy",))
    conn.execute("INSERT INTO m(content) VALUES (?)", ("unrelated note about the weather",))
    return conn


def test_hyphenated_query_now_matches_end_to_end():
    conn = _fts_db()
    built = _build_fts_prefix_query("compounding-anything")
    n = conn.execute("SELECT count(*) FROM m WHERE m MATCH ?", (built,)).fetchone()[0]
    assert n == 1  # finds the "compounding anything" doc


def test_raw_hyphenated_query_was_the_bug():
    """Demonstrates the original failure mode the fix prevents: the raw token
    with a trailing `*` is invalid FTS5 and raises."""
    conn = _fts_db()
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("SELECT count(*) FROM m WHERE m MATCH ?", ("compounding-anything*",)).fetchone()
