"""F7: Bayesian knowledge tracing, mastery bands and the class map. Pure functions; no model, no I/O."""
from __future__ import annotations

from dataclasses import dataclass

MODEL_VERSION = "bkt-v1"
P_INIT, P_LEARN, P_SLIP = 0.2, 0.15, 0.10
GUESS_SHORT_ANSWER = 0.05
K_ANONYMITY = 5
MASTERED, PROGRESSING, NEEDS_REVIEW, NOT_ENOUGH = "MASTERED", "PROGRESSING", "NEEDS_REVIEW", "NOT_ENOUGH_DATA"


def guess_for(n_choices: int | None) -> float:
    return 1.0 / n_choices if n_choices and n_choices >= 2 else GUESS_SHORT_ANSWER


def update(p_known: float, correct: bool, *, guess: float, weight: float = 1.0, slip: float = P_SLIP, learn: float = P_LEARN) -> float:
    """One BKT step. A multi-concept question passes weight < 1 and learns proportionally less."""
    if not 0.0 <= p_known <= 1.0 or not 0.0 < weight <= 1.0 or not 0.0 < guess < 1.0:
        raise ValueError("probability out of range")
    if correct:
        posterior = p_known * (1 - slip) / (p_known * (1 - slip) + (1 - p_known) * guess)
    else:
        posterior = p_known * slip / (p_known * slip + (1 - p_known) * (1 - guess))
    return posterior + (1 - posterior) * learn * weight


def band(p_known: float, attempts: int) -> str:
    if attempts < 3:
        return NOT_ENOUGH
    if p_known >= 0.95:
        return MASTERED
    if p_known >= 0.6:
        return PROGRESSING
    return NEEDS_REVIEW


@dataclass
class Mastery:
    p_known: float = P_INIT
    attempts: int = 0
    correct: int = 0

    def apply(self, correct: bool, *, guess: float, weight: float = 1.0) -> "Mastery":
        return Mastery(update(self.p_known, correct, guess=guess, weight=weight), self.attempts + 1, self.correct + int(correct))

    @property
    def band(self) -> str:
        return band(self.p_known, self.attempts)


def review_order(due_items: list[dict], mastery_by_concept: dict[str, Mastery]) -> list[dict]:
    """Due items of the lowest-mastery concept first; ties keep their original (SM-2) order. SM-2 itself is untouched."""
    def key(indexed):
        i, item = indexed
        ps = [mastery_by_concept[c].p_known for c in item.get("concept_ids", ()) if c in mastery_by_concept]
        return (min(ps) if ps else 1.0, i)
    return [item for _, item in sorted(enumerate(due_items), key=key)]


def class_map(rows: list[dict], *, k: int = K_ANONYMITY) -> list[dict]:
    """rows: {concept_id, label, student, p_known, attempts}. Per concept: counts per band; any cell under k hides its number.

    No student identifier leaves this function. A concept with fewer than k students shows no rates at all.
    """
    by_concept: dict[str, dict] = {}
    for r in rows:
        entry = by_concept.setdefault(r["concept_id"], {"label": r["label"], "students": {}})
        entry["students"][r["student"]] = band(r["p_known"], r["attempts"])
    out = []
    for cid, entry in by_concept.items():
        n = len(entry["students"])
        counts = {b: 0 for b in (MASTERED, PROGRESSING, NEEDS_REVIEW, NOT_ENOUGH)}
        for b in entry["students"].values():
            counts[b] += 1
        if n < k:
            out.append({"concept_id": cid, "label": entry["label"], "students": f"<{k}", "bands": None, "needs_review_rate": None})
        else:
            shown = {b: (c if c >= k else f"<{k}") for b, c in counts.items()}
            out.append({"concept_id": cid, "label": entry["label"], "students": n, "bands": shown,
                        "needs_review_rate": round(counts[NEEDS_REVIEW] / n, 3)})
    out.sort(key=lambda e: (e["needs_review_rate"] is None, -(e["needs_review_rate"] or 0), e["label"]))
    return out


def option_rates(attempts: list[dict], *, k: int = K_ANONYMITY) -> dict:
    """attempts: {item_id, option, correct, first}. Rates per distractor appear only for items with at least k attempts."""
    items: dict[str, list[dict]] = {}
    for a in attempts:
        items.setdefault(a["item_id"], []).append(a)
    out = {}
    for item_id, rows in items.items():
        if len(rows) < k:
            out[item_id] = {"attempts": f"<{k}", "first_try_rate": None, "options": None}
            continue
        firsts = [r for r in rows if r.get("first")]
        opts: dict[str, int] = {}
        for r in rows:
            opts[r["option"]] = opts.get(r["option"], 0) + 1
        out[item_id] = {"attempts": len(rows), "first_try_rate": round(sum(1 for r in firsts if r["correct"]) / len(firsts), 3) if len(firsts) >= k else None,
                        "options": {o: round(c / len(rows), 3) for o, c in sorted(opts.items()) if c >= k}}
    return out
