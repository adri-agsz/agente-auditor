"""
Fix Validator Agent - Final validation and report generation.

This agent compiles all results and determines if the fix was successful.
"""

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import FunctionTool
from google.adk.utils import instructions_utils
from code_review_assistant.config import config
from code_review_assistant.tools import validate_fixed_style, compile_fix_report, exit_fix_loop

# MODULE_6_STEP_3_FIX_VALIDATOR_INSTRUCTION_PROVIDER


# MODULE_6_STEP_3_FIX_VALIDATOR_AGENT