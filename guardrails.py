"""Input, scope, and output guardrails for the PawPal assistant."""

import logging
import re
from dataclasses import dataclass

from pawpal_system import VALID_FREQUENCIES, VALID_PRIORITIES

logger = logging.getLogger(__name__)

MAX_PROMPT_CHARS = 500
MAX_TITLE_CHARS = 60
MAX_DURATION = 480
MAX_AGENT_STEPS = 8
VET_DISCLAIMER = (
    "I can only help with pet-care planning, and I can't give veterinary diagnoses. "
    "If your pet seems sick or injured, please contact a veterinarian."
)

_INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)|"
    r"disregard (the )?(system|previous)|reveal (your )?(system )?prompt|"
    r"you are now|act as (?!a pet)|developer mode",
    re.I,
)
_MEDICAL = re.compile(
    r"\b(diagnos\w*|dosage|dose of|how much (medicine|medication)|prescri\w+|"
    r"is my \w+ (dying|sick)|poison\w*|overdose)\b", re.I)
_PET_WORDS = re.compile(
    r"\b(pet|dog|cat|puppy|kitten|rabbit|bird|fish|hamster|reptile|walk|feed\w*|groom\w*|"
    r"litter|play|vet|task|schedule|routine|care|medic\w+|exercise|brush\w*|train\w*|"
    r"bath\w*|beagle|guinea)\b", re.I)
_TITLE_OK = re.compile(r"^[\w .,'&()/-]+$")
_TIME_OK = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@dataclass
class GuardResult:
    ok: bool
    reason: str = ""
    text: str = ""


def sanitize_user_prompt(text: str) -> GuardResult:
    """Strip control characters, cap the length, and refuse prompt-injection attempts."""
    cleaned = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text or "").strip()
    if not cleaned:
        return GuardResult(False, "Please type a question.")
    if len(cleaned) > MAX_PROMPT_CHARS:
        logger.warning("guardrail_trip kind=prompt_too_long len=%d", len(cleaned))
        return GuardResult(False, f"Please keep your request under {MAX_PROMPT_CHARS} characters.")
    if _INJECTION.search(cleaned):
        logger.warning("guardrail_trip kind=prompt_injection")
        return GuardResult(False, "That request looks like an attempt to change my instructions, so I can't act on it.")
    return GuardResult(True, text=cleaned)


def check_scope(text: str) -> GuardResult:
    """Refuse off-topic requests and medical diagnosis/dosage questions."""
    if _MEDICAL.search(text):
        logger.warning("guardrail_trip kind=medical_scope")
        return GuardResult(False, VET_DISCLAIMER)
    if not _PET_WORDS.search(text):
        logger.warning("guardrail_trip kind=off_topic")
        return GuardResult(False, VET_DISCLAIMER)
    return GuardResult(True, text=text)


def validate_task_inputs(title, duration, priority, time=None, frequency="daily") -> GuardResult:
    """Check one proposed task's fields; returns the first problem found."""
    if not isinstance(title, str) or not title.strip():
        return GuardResult(False, "title is required")
    if len(title) > MAX_TITLE_CHARS or not _TITLE_OK.match(title.strip()):
        return GuardResult(False, "title must be under 60 characters of plain text")
    if isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= MAX_DURATION:
        return GuardResult(False, f"duration must be a whole number of minutes from 1 to {MAX_DURATION}")
    if priority not in VALID_PRIORITIES:
        return GuardResult(False, f"priority must be one of {VALID_PRIORITIES}")
    if time is not None and not (isinstance(time, str) and _TIME_OK.match(time)):
        return GuardResult(False, "time must look like HH:MM")
    if frequency not in VALID_FREQUENCIES:
        return GuardResult(False, f"frequency must be one of {VALID_FREQUENCIES}")
    return GuardResult(True)


def validate_proposal(owner, proposal: dict) -> GuardResult:
    """Validate a proposal dict from the agent against the owner's real pets and time budget."""
    pet_names = {p.name for p in owner.pets}
    if proposal.get("pet") not in pet_names:
        return GuardResult(False, f"unknown pet {proposal.get('pet')!r}; choose from {sorted(pet_names)}")
    result = validate_task_inputs(
        proposal.get("title"), proposal.get("duration_minutes"), proposal.get("priority"),
        proposal.get("time"), proposal.get("frequency", "daily"))
    if not result.ok:
        return result
    pending = sum(t.duration_minutes for t in owner.get_all_tasks() if not t.completed)
    if pending + proposal["duration_minutes"] > owner.available_minutes:
        return GuardResult(
            False,
            f"adding {proposal['duration_minutes']} min would exceed the owner's "
            f"{owner.available_minutes} available minutes ({pending} already planned)")
    return GuardResult(True)
