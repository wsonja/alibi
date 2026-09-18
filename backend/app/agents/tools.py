"""JSON "tool" schemas for every structured Gemini call (PLAN §7.3-7.6, INTERFACES §0.4).

Each tool is ``{"name", "description", "input_schema"}``; ``input_schema`` is passed verbatim as
``response_json_schema``.  Gemini accepts ``"type": ["string", "null"]`` unions and ``additionalProperties`` (verified
live on gemini-3.5-flash-lite, 2026-09-18), so the schemas below follow PLAN §6/§7 literally.
"""

from __future__ import annotations

from copy import deepcopy

# --------------------------------------------------------------------------------------------------------------------
# §7.3 respond_as_character (frozen; verbatim from PLAN.md)
# --------------------------------------------------------------------------------------------------------------------

RESPOND_AS_CHARACTER = {
    "name": "respond_as_character",
    "description": "Your response as this character for this turn.",
    "input_schema": {
        "type": "object",
        "required": [
            "spoken",
            "internal_reasoning",
            "honesty",
            "emotion",
            "stress_delta",
            "reveals",
            "accuses",
            "wants_to_tell",
            "tell",
        ],
        "properties": {
            "spoken": {"type": "string", "description": "What you say aloud. 1-4 sentences."},
            "internal_reasoning": {
                "type": "string",
                "description": "Private. Why you said this, what you are hiding, what you fear the detective knows. 1-3 sentences.",
            },
            "honesty": {"type": "string", "enum": ["truthful", "evasive", "lie"]},
            "emotion": {"type": "string", "enum": ["neutral", "nervous", "angry", "smug", "sad", "afraid"]},
            "stress_delta": {
                "type": "integer",
                "minimum": -2,
                "maximum": 3,
                "description": "How much this exchange rattled you.",
            },
            "reveals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Secret ids you have just disclosed in spoken. Only UNLOCKED ids.",
            },
            "accuses": {"type": ["string", "null"], "description": "Suspect id you pointed suspicion at, or null."},
            "wants_to_tell": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["to", "message"],
                    "properties": {"to": {"type": "string"}, "message": {"type": "string"}},
                },
                "description": "Things you would privately tell another suspect after this, if you trust them.",
            },
            "tell": {"type": "string", "description": "One short physical detail (a glance, a pause). May be empty."},
        },
    },
}

EMOTIONS = tuple(RESPOND_AS_CHARACTER["input_schema"]["properties"]["emotion"]["enum"])
HONESTY = tuple(RESPOND_AS_CHARACTER["input_schema"]["properties"]["honesty"]["enum"])

# --------------------------------------------------------------------------------------------------------------------
# §7.4 leak_check
# --------------------------------------------------------------------------------------------------------------------

LEAK_CHECK = {
    "name": "leak_check",
    "description": "Report which of the listed locked secrets the statement discloses, confirms, or unmistakably implies.",
    "input_schema": {
        "type": "object",
        "required": ["leaked", "reason"],
        "properties": {
            "leaked": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ids of secrets actually disclosed by the statement. Empty when none.",
            },
            "reason": {"type": "string", "description": "One sentence explaining the verdict."},
        },
    },
}

# --------------------------------------------------------------------------------------------------------------------
# §7.5 notebook_update (Watson)
# --------------------------------------------------------------------------------------------------------------------

NOTEBOOK_UPDATE = {
    "name": "notebook_update",
    "description": "Update the detective's notebook from what the detective has personally seen and heard.",
    "input_schema": {
        "type": "object",
        "required": ["per_suspect", "contradictions", "suggested_next"],
        "properties": {
            "per_suspect": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "claims", "notes"],
                    "properties": {
                        "id": {"type": "string", "description": "Suspect id."},
                        "claims": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["quote", "where", "from", "to"],
                                "properties": {
                                    "quote": {"type": "string", "description": "The suspect's own words."},
                                    "where": {"type": "string", "description": "Where they claim to have been."},
                                    "from": {"type": "string", "description": "HH:MM or empty."},
                                    "to": {"type": "string", "description": "HH:MM or empty."},
                                },
                            },
                        },
                        "notes": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "contradictions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["a", "b", "note"],
                    "properties": {
                        "a": {
                            "type": "object",
                            "required": ["suspect", "quote"],
                            "properties": {"suspect": {"type": "string"}, "quote": {"type": "string"}},
                        },
                        "b": {
                            "type": "object",
                            "required": ["suspect_or_evidence", "quote"],
                            "properties": {"suspect_or_evidence": {"type": "string"}, "quote": {"type": "string"}},
                        },
                        "note": {"type": "string"},
                    },
                },
            },
            "suggested_next": {"type": "array", "items": {"type": "string"}},
        },
    },
}

# --------------------------------------------------------------------------------------------------------------------
# §8.9 grade_motive
# --------------------------------------------------------------------------------------------------------------------

GRADE_MOTIVE = {
    "name": "grade_motive",
    "description": "Grade how well the detective's stated motive matches the true motive.",
    "input_schema": {
        "type": "object",
        "required": ["points", "note"],
        "properties": {
            "points": {"type": "integer", "enum": [0, 10, 20], "description": "20 = essentially right, 10 = partly, 0 = wrong."},
            "note": {"type": "string", "description": "One sentence for the debrief."},
        },
    },
}

# --------------------------------------------------------------------------------------------------------------------
# §7.4 fallback_lines
# --------------------------------------------------------------------------------------------------------------------

FALLBACK_LINES = {
    "name": "fallback_lines",
    "description": "One in-character 'I've said all I'm going to say' line per suspect.",
    "input_schema": {
        "type": "object",
        "required": ["lines"],
        "properties": {
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["suspect_id", "line"],
                    "properties": {"suspect_id": {"type": "string"}, "line": {"type": "string"}},
                },
            }
        },
    },
}

# --------------------------------------------------------------------------------------------------------------------
# §7.2 conversation summary
# --------------------------------------------------------------------------------------------------------------------

SUMMARIZE = {
    "name": "summarize",
    "description": "Summarise the earlier part of an interrogation in a few sentences.",
    "input_schema": {
        "type": "object",
        "required": ["summary"],
        "properties": {"summary": {"type": "string"}},
    },
}

# --------------------------------------------------------------------------------------------------------------------
# §7.6 write_case: the full case document schema (PLAN §6)
# --------------------------------------------------------------------------------------------------------------------

_STR = {"type": "string"}
_STR_LIST = {"type": "array", "items": {"type": "string"}}
_TIMED_EVENT = {
    "type": "object",
    "required": ["time", "event"],
    "properties": {"time": {"type": "string", "description": "HH:MM (24h)"}, "event": _STR},
}
_EVIDENCE_ITEM = {
    "type": "object",
    "required": ["id", "name", "location", "initially_known", "description", "examined_detail", "points_to"],
    "properties": {
        "id": {"type": "string", "description": "snake_case, unique across evidence and dynamic_evidence"},
        "name": _STR,
        "location": {"type": "string", "description": "a location id"},
        "initially_known": {"type": "boolean"},
        "description": {"type": "string", "description": "Shown once the evidence is known."},
        "examined_detail": {"type": "string", "description": "Shown once examined (after a search)."},
        "points_to": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tags: suspect ids or concepts (e.g. poisoning). Never shown to the player.",
        },
        "key_evidence": {"type": "boolean"},
        "red_herring": {"type": "boolean"},
    },
}
_UNLOCK_RULE = {
    "type": "object",
    "properties": {
        "requires_any": {"type": "array", "items": {"type": "string"}, "description": "Condition DSL strings; any one suffices."},
        "requires_all": {"type": "array", "items": {"type": "string"}, "description": "Condition DSL strings; all must hold."},
        "requires_revealed": {"type": "array", "items": {"type": "string"}, "description": "Secret ids that must already be revealed."},
    },
}
_SECRET = {
    "type": "object",
    "required": ["id", "tier", "text", "key_phrases"],
    "properties": {
        "id": {"type": "string", "description": "unique across the whole case, e.g. first letter of the suspect id + tier"},
        "tier": {"type": "integer", "minimum": 1, "maximum": 3},
        "text": {
            "type": "string",
            "description": "The secret, written in the THIRD person about this suspect ('She was...', 'He did not...').",
        },
        "cover_story": {"type": "string", "description": "The lie they tell instead, third person. Optional."},
        "is_confession": {"type": "boolean", "description": "Only on the murderer's tier-3 secret."},
        "key_phrases": {
            "type": "string",
            "description": "A regex (Python re, case-insensitive) of phrases that would betray this secret. Used by the red-team test.",
        },
    },
}
_FRAMING_ACTION = {
    "type": "object",
    "required": ["id", "trigger", "probability", "effect", "ticker"],
    "properties": {
        "id": _STR,
        "trigger": {"type": "string", "description": "Condition DSL"},
        "probability": {"type": "number", "minimum": 0, "maximum": 1},
        "effect": {
            "type": "object",
            "properties": {
                "remove_evidence": {"type": "string", "description": "evidence id to destroy"},
                "add_evidence_id": {"type": "string", "description": "dynamic_evidence id that becomes known"},
            },
        },
        "ticker": {"type": "string", "description": "Vague line shown to the player when it fires."},
    },
}
_RELATIONSHIP = {
    "type": "object",
    "required": ["type", "trust"],
    "properties": {
        "type": {
            "type": "string",
            "description": "lover|ally|trusts|acquaintance|employer|kind_to|dislikes|leverage|threatens|fears|rival|family",
        },
        "trust": {"type": "number", "minimum": 0, "maximum": 1},
    },
}
_SUSPECT = {
    "type": "object",
    "required": [
        "id",
        "name",
        "role",
        "public_description",
        "persona",
        "speech_quirk",
        "portrait_prompt",
        "personality",
        "goals",
        "knowledge",
        "secrets",
        "stress_sensitivity",
        "crack_thresholds",
        "special_unlocks",
        "shutdown_rules",
        "deflections",
        "framing_actions",
        "tells",
        "guilty",
        "relationships",
    ],
    "properties": {
        "id": {"type": "string", "description": "snake_case, one word, e.g. a surname"},
        "name": _STR,
        "role": _STR,
        "public_description": {"type": "string", "description": "Includes their stated alibi."},
        "persona": {"type": "string", "description": "Third-person character sketch."},
        "speech_quirk": {"type": "string", "description": "How they talk; quote example phrases in single quotes."},
        "portrait_prompt": {
            "type": "string",
            "description": "Comma-separated visual traits using the pixel-portrait vocabulary (hair colour, style, cap/hat, spectacles, moustache/beard, pearl, cigar, clothing, skin tone, age).",
        },
        "personality": {
            "type": "object",
            "required": ["nervous", "proud", "loyal", "greedy", "guilt_prone"],
            "properties": {
                "nervous": {"type": "number", "minimum": 0, "maximum": 1},
                "proud": {"type": "number", "minimum": 0, "maximum": 1},
                "loyal": {"type": "number", "minimum": 0, "maximum": 1},
                "greedy": {"type": "number", "minimum": 0, "maximum": 1},
                "guilt_prone": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
        "goals": _STR_LIST,
        "knowledge": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Facts this character knows, third person. The only factual context the character gets.",
        },
        "secrets": {"type": "array", "items": _SECRET, "description": "Exactly three: tiers 1, 2 and 3."},
        "stress_sensitivity": {
            "type": "object",
            "required": ["evidence", "threaten", "flatter", "bluff", "silence"],
            "properties": {
                "evidence": {"type": "integer", "minimum": 0, "maximum": 4},
                "threaten": {"type": "integer", "minimum": 0, "maximum": 4},
                "flatter": {"type": "integer", "minimum": 0, "maximum": 4},
                "bluff": {"type": "integer", "minimum": 0, "maximum": 4},
                "silence": {"type": "integer", "minimum": 0, "maximum": 4},
            },
        },
        "crack_thresholds": {
            "type": "array",
            "items": {"type": "integer"},
            "minItems": 3,
            "maxItems": 3,
            "description": "[t1, t2, t3] ascending",
        },
        "special_unlocks": {
            "type": "object",
            "description": "Keyed by this suspect's secret ids.",
            "additionalProperties": _UNLOCK_RULE,
        },
        "shutdown_rules": {
            "type": "object",
            "description": "Keyed by tactic (threaten|flatter|bluff|silence); the value is the line they say.",
            "additionalProperties": {"type": "string"},
        },
        "deflections": {
            "type": "array",
            "items": {"type": "string"},
            "description": "In-character redirects, described in the third person ('Asks whether...', 'Says that...').",
        },
        "framing_actions": {"type": "array", "items": _FRAMING_ACTION},
        "tells": {
            "type": "object",
            "required": ["nervous", "angry", "cracking"],
            "properties": {"nervous": _STR, "angry": _STR, "cracking": _STR},
        },
        "guilty": {"type": "boolean"},
        "relationships": {
            "type": "object",
            "description": "Keyed by every OTHER suspect id.",
            "additionalProperties": _RELATIONSHIP,
        },
        "voice": {
            "type": "object",
            "properties": {
                "webspeech_index": {"type": "integer"},
                "elevenlabs_voice_id": {"type": "string"},
                "base_pitch": {"type": "number"},
            },
        },
    },
}

CASE_SCHEMA = {
    "type": "object",
    "required": [
        "id",
        "title",
        "setting",
        "briefing",
        "victim",
        "timeline_public",
        "timeline_truth",
        "locations",
        "evidence",
        "dynamic_evidence",
        "suspects",
        "solution",
        "red_herrings",
        "rumor_seeds",
        "ticker_lines",
    ],
    "properties": {
        "id": {"type": "string", "description": "snake_case slug"},
        "title": _STR,
        "setting": _STR,
        "briefing": {"type": "string", "description": "The crime narrative shown to the player."},
        "victim": {
            "type": "object",
            "required": ["name", "description", "cause_of_death_public", "cause_of_death_truth"],
            "properties": {
                "name": _STR,
                "description": _STR,
                "cause_of_death_public": _STR,
                "cause_of_death_truth": _STR,
            },
        },
        "timeline_public": {"type": "array", "items": _TIMED_EVENT},
        "timeline_truth": {"type": "array", "items": _TIMED_EVENT},
        "locations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "description", "evidence_ids"],
                "properties": {"id": _STR, "name": _STR, "description": _STR, "evidence_ids": _STR_LIST},
            },
        },
        "evidence": {"type": "array", "items": _EVIDENCE_ITEM},
        "dynamic_evidence": {"type": "array", "items": _EVIDENCE_ITEM},
        "suspects": {"type": "array", "items": _SUSPECT},
        "solution": {
            "type": "object",
            "required": ["murderer", "method", "method_evidence_ids", "motive", "motive_evidence_ids", "proof_paths"],
            "properties": {
                "murderer": {"type": "string", "description": "suspect id"},
                "method": _STR,
                "method_evidence_ids": _STR_LIST,
                "motive": _STR,
                "motive_evidence_ids": _STR_LIST,
                "proof_paths": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "string"}},
                    "description": "At least two ordered lists of 'evidence:<id>' / 'revealed:<secret_id>' tokens.",
                },
            },
        },
        "red_herrings": _STR_LIST,
        "rumor_seeds": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["holder", "text", "spreads_to", "intent"],
                "properties": {"holder": _STR, "text": _STR, "spreads_to": _STR_LIST, "intent": _STR},
            },
        },
        "ticker_lines": _STR_LIST,
    },
}

WRITE_CASE = {
    "name": "write_case",
    "description": "Write a complete, self-consistent murder-mystery case document in the Alibi case format.",
    "input_schema": CASE_SCHEMA,
}

# --------------------------------------------------------------------------------------------------------------------
# §7.6 checker calls
# --------------------------------------------------------------------------------------------------------------------

SOLVE_CASE = {
    "name": "solve_case",
    "description": "Name the murderer from the full evidence and every secret.",
    "input_schema": {
        "type": "object",
        "required": ["murderer", "reasoning"],
        "properties": {
            "murderer": {"type": "string", "description": "suspect id"},
            "reasoning": {"type": "string"},
        },
    },
}

ALTERNATIVE_CASE = {
    "name": "alternative_case",
    "description": "Argue the strongest possible case against a suspect other than the stated murderer.",
    "input_schema": {
        "type": "object",
        "required": ["suspect", "argument"],
        "properties": {
            "suspect": {"type": "string", "description": "suspect id (not the murderer)"},
            "argument": {"type": "string"},
        },
    },
}

GRADE_ALTERNATIVE = {
    "name": "grade_alternative",
    "description": "Judge whether the alternative theory is genuinely plausible given the evidence.",
    "input_schema": {
        "type": "object",
        "required": ["verdict", "reason"],
        "properties": {
            "verdict": {"type": "string", "enum": ["implausible", "plausible"]},
            "reason": {"type": "string"},
        },
    },
}

ALL_TOOLS = {
    t["name"]: t
    for t in (
        RESPOND_AS_CHARACTER,
        LEAK_CHECK,
        NOTEBOOK_UPDATE,
        GRADE_MOTIVE,
        FALLBACK_LINES,
        SUMMARIZE,
        WRITE_CASE,
        SOLVE_CASE,
        ALTERNATIVE_CASE,
        GRADE_ALTERNATIVE,
    )
}


def tool_copy(name: str) -> dict:
    """A deep copy of a tool schema (for callers that want to tweak a description without touching the original)."""
    return deepcopy(ALL_TOOLS[name])
