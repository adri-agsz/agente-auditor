"""
Fix Synthesizer Agent - Generates user-friendly fix summary.

This agent creates the final, comprehensive response about the fix process.
"""

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import FunctionTool
from google.adk.utils import instructions_utils
from code_review_assistant.config import config
from code_review_assistant.tools import save_fix_report


# MODULE_6_STEP_6_FIX_SYNTHESIZER_INSTRUCTION_PROVIDER


# MODULE_6_STEP_6_FIX_SYNTHESIZER_AGENT