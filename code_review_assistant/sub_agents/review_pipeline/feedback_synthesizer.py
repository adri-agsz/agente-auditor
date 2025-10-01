"""
Feedback Synthesizer Agent - Provides comprehensive, personalized feedback.

This agent synthesizes all analysis results into constructive feedback,
incorporating past feedback history and tracking improvement over time.
"""

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import FunctionTool
from google.adk.utils import instructions_utils
from code_review_assistant.config import config
from code_review_assistant.tools import search_past_feedback, update_grading_progress, save_grading_report


# MODULE_5_STEP_4_INSTRUCTION_PROVIDER


# MODULE_5_STEP_4_SYNTHESIZER_AGENT