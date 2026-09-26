"""Word error rate (WER) for STT acceptance tests (BUILD_PLAN section 9/10).

Standard Levenshtein alignment over words, divided by reference word count.
No external dependency so CI can compute it on any OS.
"""

from __future__ import annotations

import re


def normalize(text: str) -> list[str]:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s']", " ", text)
    return [w for w in text.split() if w]


def wer(reference: str, hypothesis: str) -> float:
    """WER of ``hypothesis`` vs ``reference`` (0.0 = perfect, can exceed 1.0)."""
    ref = normalize(reference)
    hyp = normalize(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    # classic DP: edits (sub/ins/del) over ref words
    d = [[0] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    for i in range(len(ref) + 1):
        d[i][0] = i
    for j in range(len(hyp) + 1):
        d[0][j] = j
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
    return d[len(ref)][len(hyp)] / len(ref)


def aggregate_wer(pairs: list[tuple[str, str]]) -> float:
    """Micro-average WER over (reference, hypothesis) pairs."""
    total_edits = 0.0
    total_words = 0
    for ref, hyp in pairs:
        r = normalize(ref)
        total_words += len(r)
        total_edits += wer(ref, hyp) * len(r)
    return total_edits / total_words if total_words else 0.0
