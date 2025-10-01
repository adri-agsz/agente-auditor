"""
Style Checker Agent - Validates PEP 8 compliance.

This agent checks Python code style against PEP 8 guidelines using
pycodestyle, identifying violations and calculating a style score.
"""

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import FunctionTool
from google.adk.utils import instructions_utils
from code_review_assistant.config import config
from code_review_assistant.tools import check_code_style


# MODULE_5_STEP_1_INSTRUCTION_PROVIDER


# MODULE_5_STEP_1_STYLE_CHECKER_AGENT