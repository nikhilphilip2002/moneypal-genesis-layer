"""Answer synthesis for the mailbox console.

Retrieval is done by :mod:`app.services.email_intel`; this module only turns the retrieved
passages into prose. The provider credentials and model mirror the email service's own
.env (NVIDIA Nemotron by default — that .env defines LLM_PROVIDER/LLM_MODEL twice and
the last definition wins, leaving the earlier Groq block unused).

Two providers are configured and neither is reliable enough to be the only one: NVIDIA
returns 503 under load and Groq is intermittently refused with 403 by its edge. So the
module keeps a small health table and fails over in both directions automatically — a
provider that errors is benched for a growing cooldown while the other is tried, and the
one that last worked is preferred on the next question. Nothing here is configured by hand.

Every failure mode degrades rather than raises: if both providers are down, the caller
still gets its cited passages and simply has no narrative. A mailbox console that
hard-fails because a third-party API is down is worse than one that shows the evidence.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from app.core.config import settings

_SYSTEM = (
    "You are a credit-operations analyst for a bank's GICC team. You answer questions using "
    "only the email excerpts supplied. Rules: never invent facts, dates, amounts or senders; "
    "if the excerpts do not contain the answer, say so plainly; keep the answer under 200 words; "
    "refer to messages by subject and sender."
)

_FALLBACK = "The answer model is unavailable, so only the matching passages are shown."

# A provider is benched for BASE_COOLDOWN seconds, doubling per consecutive failure up to
# MAX_COOLDOWN. Long enough that a brief 503 burst costs one provider for a while rather
# than flapping between them on every question.
BASE_COOLDOWN = 30.0
MAX_COOLDOWN = 300.0


@dataclass
class _Health:
    """Rolling health for one provider. Guarded by _LOCK."""

    consecutive_failures: int = 0
    benched_until: float = 0.0
    last_success: float = 0.0
    last_error: str = ""

    def benched(self, now: float) -> bool:
        return now < self.benched_until

    def cooldown(self) -> float:
        return min(BASE_COOLDOWN * (2 ** max(0, self.consecutive_failures - 1)), MAX_COOLDOWN)

    def record_success(self, now: float) -> None:
        self.consecutive_failures = 0
        self.benched_until = 0.0
        self.last_success = now
        self.last_error = ""

    def record_failure(self, now: float, error: str, hard: bool = False) -> None:
        self.consecutive_failures += 1
        if hard:
            # 401/403 means the credential or the edge is refusing us. Retrying that in
            # 30s achieves nothing, so the provider is benched for the full window and
            # the other one carries the load until it is worth probing again.
            self.benched_until = now + MAX_COOLDOWN
        else:
            self.benched_until = now + self.cooldown()
        self.last_error = error


_LOCK = threading.Lock()
_HEALTH: dict[str, _Health] = {}
# Which provider actually produced the most recent narrative. Thread-local so concurrent
# questions cannot mislabel each other's answer_model.
_LAST = threading.local()


def served_by() -> str | None:
    """Provider that produced the last narrative, or None if synthesis did not run."""
    return getattr(_LAST, "provider", None)


def _configured() -> dict[str, tuple[str, str | None]]:
    """provider name -> (base_url, api_key), for every provider with a key present."""
    out: dict[str, tuple[str, str | None]] = {}
    if settings.email_llm_api_key and settings.email_llm_base_url:
        out["nvidia"] = (settings.email_llm_base_url, settings.email_llm_api_key)
    if settings.groq_api_key and settings.groq_base_url:
        out["groq"] = (settings.groq_base_url, settings.groq_api_key)
    return out


def _model_for(name: str) -> str:
    return settings.email_llm_model if name == "nvidia" else settings.groq_model


def _order(now: float) -> list[str]:
    """Providers to try this time: usable first, then benched ones as a last resort.

    Usable providers are ordered by most-recent success, so the console keeps using
    whichever provider is currently working without any reconfiguration. When every
    provider is benched the order is preserved rather than empty, because refusing to try
    at all would turn a transient outage into a permanent one.
    """
    names = list(_configured())
    health = {n: _HEALTH.setdefault(n, _Health()) for n in names}

    def key(name: str) -> tuple[int, float, int]:
        h = health[name]
        if h.benched(now):
            return (2, h.benched_until, names.index(name))
        # Never succeeded yet sorts after those that have, so a recovered provider wins.
        return (0 if h.last_success else 1, -h.last_success, names.index(name))

    return sorted(names, key=key)


def snapshot() -> list[dict]:
    """Current provider health, for diagnostics and the console's model label."""
    now = time.monotonic()
    with _LOCK:
        return [
            {
                "provider": name,
                "model": _model_for(name),
                "benched": _HEALTH.setdefault(name, _Health()).benched(now),
                "consecutive_failures": _HEALTH.setdefault(name, _Health()).consecutive_failures,
                "last_error": _HEALTH.setdefault(name, _Health()).last_error,
            }
            for name in _configured()
        ]


def preferred() -> str | None:
    """The provider that will be tried first, or None when no key is configured."""
    order = _order(time.monotonic())
    return order[0] if order else None


def _endpoint(base_url: str) -> str:
    return base_url.rstrip("/") + "/chat/completions"


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _build_messages(question: str, passages: list[dict]) -> list[dict]:
    excerpts = []
    for i, hit in enumerate(passages, start=1):
        excerpts.append(
            f"[{i}] subject={hit.get('subject')!r} sender={hit.get('sender')!r} "
            f"date={hit.get('date')!r} part={hit.get('filename')!r} "
            f"score={hit.get('score')}\n{(hit.get('text') or '').strip()}"
        )
    user = (
        f"Question: {question}\n\nEmail excerpts:\n" + "\n\n".join(excerpts)
        + "\n\nAnswer using only these excerpts."
    )
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]


def available() -> bool:
    """True when any provider key is configured, so the UI can label the model honestly."""
    return bool(_configured())


def model_name() -> str | None:
    """The model that will be tried first, for display in the UI.

    Tracks the pool's current preference, so when failover has moved the console onto the
    other provider the label follows it instead of naming a provider that is benched.
    """
    first = preferred()
    return _model_for(first) if first else None


def _call(provider: str, base_url: str, api_key: str, model: str,
          messages: list[dict]) -> tuple[str | None, str | None, bool]:
    """Return ``(text, error, hard)``.

    ``hard`` marks a refusal (401/403) as opposed to an overload or network blip, so the
    pool can bench the provider for longer. A bad key does not become a good key.
    """
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": settings.email_llm_max_tokens,
    }
    request = urllib.request.Request(
        _endpoint(base_url),
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(api_key),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.email_llm_timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            pass
        hard = exc.code in (401, 403)
        suffix = " (credential refused)" if hard else ""
        return None, f"{provider} returned HTTP {exc.code}{suffix}. {detail}".strip(), hard
    except urllib.error.URLError as exc:
        return None, f"{provider} unreachable: {exc.reason}", False
    except Exception as exc:  # noqa: BLE001 - degrade rather than break the console
        return None, f"{provider} failed: {exc}", False

    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None, f"{provider} returned an unexpected response shape.", False
    if not isinstance(text, str) or not text.strip():
        return None, f"{provider} returned an empty answer.", False
    return text.strip(), None, False


def answer(question: str, passages: list[dict]) -> tuple[str | None, str | None]:
    """Return ``(narrative, error)``.

    Providers are tried in the pool's current order, which is whichever one last worked
    unless it is inside a failure cooldown. A provider that errors — 403, 503, unreachable,
    junk payload — is benched and the next one is tried, so a dead NVIDIA hands over to
    Groq and a dead Groq hands back to NVIDIA without any configuration. A success clears
    the cooldown and returns that provider to the front of the order.

    On total failure ``(None, errors)`` is returned so the caller can still show its cited
    passages.
    """
    if not passages:
        return None, "No matching mailbox message to answer from."

    configured = _configured()
    if not configured:
        return None, "No answer-model credential is configured (EMAIL_LLM_API_KEY or GROQ_API_KEY)."

    messages = _build_messages(question, passages)
    order = _order(time.monotonic())
    errors: list[str] = []

    def _try(name: str) -> str | None:
        base_url, api_key = configured[name]
        text, error, hard = _call(name, base_url, api_key or "", _model_for(name), messages)
        if text:
            with _LOCK:
                _HEALTH.setdefault(name, _Health()).record_success(time.monotonic())
            _LAST.provider = name
            return text
        errors.append(error or f"{name} failed")
        with _LOCK:
            _HEALTH.setdefault(name, _Health()).record_failure(
                time.monotonic(), error or "", hard
            )
        return None

    # First pass follows the pool's order (healthy providers first, benched ones last).
    # The second pass re-tries whatever is left, so a provider whose cooldown has not
    # yet expired is still given a chance rather than being written off for the process
    # lifetime. That retry is what lets the pool heal itself after an outage.
    for name in order:
        text = _try(name)
        if text:
            return text, None
    for name in order:
        text = _try(name)
        if text:
            return text, None

    _LAST.provider = None
    # The retry pass can hit the same provider again; report each distinct cause once.
    return None, " · ".join(dict.fromkeys(errors)) or _FALLBACK
