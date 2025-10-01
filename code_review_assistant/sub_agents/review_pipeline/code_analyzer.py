"""
Code Analyzer Agent - Understands code structure and complexity.

This agent is responsible for parsing and analyzing Python code structure,
identifying functions, classes, imports, and potential issues.
"""

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from code_review_assistant.config import config
from code_review_assistant.tools import analyze_code_structure


# MODULE_4_STEP_5_CREATE_AGENT