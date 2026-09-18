"""agents/ — the only package that talks to Google Gemini (docs/INTERFACES.md §3).

Public surface:
  client.call_tool / credential_available / resolve_mode / InvalidOutput / LLMUnavailable / NotConfigured
  performer.get_performer / get_scripted_performer
  suspect.build_system_blocks / GeminiPerformer
  scripted.ScriptedPerformer
  leak_guard.check
  watson.update
  judge.grade_motive / fallback_lines / summarize
  author.write_case
  checker.static_check / llm_check / run_author_with_checks
"""

from .client import InvalidOutput, LLMError, LLMUnavailable, NotConfigured, credential_available, resolve_mode
from .performer import get_performer, get_scripted_performer

__all__ = [
    "InvalidOutput",
    "LLMError",
    "LLMUnavailable",
    "NotConfigured",
    "credential_available",
    "get_performer",
    "get_scripted_performer",
    "resolve_mode",
]
