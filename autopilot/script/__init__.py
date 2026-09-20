"""Script generation, fact-checking, and validation exports."""

from autopilot.script.factcheck import run_factcheck_pass
from autopilot.script.generate import (
    build_script_prompt,
    generate_and_validate_script,
)
from autopilot.script.validate import (
    ScriptValidationError,
    count_spoken_words,
    validate_script,
)

__all__ = [
    "build_script_prompt",
    "generate_and_validate_script",
    "run_factcheck_pass",
    "validate_script",
    "count_spoken_words",
    "ScriptValidationError",
]
