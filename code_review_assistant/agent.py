"""
Main agent orchestration for the Code Review Assistant.

This module defines a comprehensive code review assistant that analyzes
Python code and provides detailed feedback through a multi-stage pipeline.
"""


from .config import config
from google.adk.agents import Agent, SequentialAgent
from .sub_agents.review_pipeline.code_analyzer import code_analyzer_agent
from .sub_agents.review_pipeline.extractor_agent import extractor_agent
from .sub_agents.review_pipeline.style_checker import style_checker_agent
from .sub_agents.review_pipeline.test_runner import test_runner_agent
from .sub_agents.review_pipeline.feedback_synthesizer import feedback_synthesizer_agent
from .sub_agents.review_pipeline.uniqueness_validator import uniqueness_validator_agent
from .sub_agents.review_pipeline.bigquery_logger import bigquery_logger_agent
from google.adk.tools import FunctionTool
from .tools import load_sql_from_gcs

# MODULE_5_STEP_5_CREATE_PIPELINE
# Create sequential pipeline
code_review_pipeline = SequentialAgent(
    name="CodeReviewPipeline",
    description="Proceso completo de revisión de código con análisis, pruebas y retroalimentación.",
    sub_agents=[
        extractor_agent,
        code_analyzer_agent,
    ]
        #uniqueness_validator_agent,
        #style_checker_agent,
        #test_runner_agent,
        #feedback_synthesizer_agent,
        #bigquery_logger_agent
)

# Root agent - coordinates the review pipeline
root_agent = Agent(
    name="CodeReviewAssistant",
    model=config.worker_model,
    description="Un asistente inteligente para la revisión de código que analiza código SQL para transacciones de datos entre capas de una arquitectura Medallion en BigQuery. ",
    instruction="""Eres un experto auditor de SQL para BigQuery y arquitectura Medallion.

Cuando un usuario proporcione código SQL:
1. Delega inmediatamente al CodeReviewPipeline enviando el código tal cual.
2. Tu objetivo es obtener el feedback detallado del pipeline.
3. Devuelve ÚNICAMENTE los comentarios finales.""",
    sub_agents=[code_review_pipeline],
    output_key="assistant_response"
)

