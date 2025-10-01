"""
Fix Test Runner Agent - Validates fixes by running tests on corrected code.

This agent executes the same test suite on the fixed code to verify
that all issues have been resolved.
"""

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.utils import instructions_utils
from code_review_assistant.config import config


# MODULE_6_STEP_2_FIX_TEST_RUNNER_INSTRUCTION_PROVIDER


# MODULE_6_STEP_2_FIX_TEST_RUNNER_AGENT