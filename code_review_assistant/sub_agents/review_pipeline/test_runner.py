"""
Test Runner Agent - Generates and executes tests using built-in code executor.

This agent generates appropriate test cases based on code analysis
and runs them using ADK's built-in code executor.
"""

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.utils import instructions_utils
from code_review_assistant.config import config


# MODULE_5_STEP_2_INSTRUCTION_PROVIDER


# MODULE_5_STEP_2_TEST_RUNNER_AGENT