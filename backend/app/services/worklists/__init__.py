"""Worklists: the end of a drill chain, where an answer becomes something a team does.

An answer that stops at a chart is not usable by a collections team. "Branch 7 is the worst"
is where the reporting product ends and where the work begins, and the step from there to
"here are the forty accounts to call this morning, in order, with the reason for each" is the
one this product exists to make.

Three properties hold throughout, and each is a decision rather than an implementation
detail:

**Every row states why it is there.** A ranked list with no reasons gets worked from the top
until the officer disagrees with one entry, and then abandoned. A row that says "184 days
since the last receipt, with ₹2.4L overdue" survives that test, because the officer can check
it.

**The ranking is arithmetic, not judgement.** The weights live in `worklists.yaml`, the
components are on the card, and the score can be recomputed by hand. No model ranks anything.

**The action comes from the bank's own policy.** Playbooks are ratified config. The assistant
retrieves the bank's collections policy; it does not compose collections advice, which is
neither its expertise nor its liability.
"""

from app.services.worklists.runner import (
    WorklistError,
    build,
    presets,
    to_csv,
)
from app.services.worklists.score import prioritise

__all__ = ["WorklistError", "build", "presets", "prioritise", "to_csv"]
