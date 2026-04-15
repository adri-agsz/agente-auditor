"""
BigQuery Logger Agent - Saves review results to BigQuery.
"""

import json
import logging
import re
from datetime import datetime
from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import FunctionTool
from ...config import config
from ...tools import save_review_to_bigquery, save_analysis_to_gcs
from ...constants import StateKeys
from google.adk.utils import instructions_utils

logger = logging.getLogger(__name__)

async def bigquery_logger_instruction_provider(context: ReadonlyContext) -> str:

    """Instrucción dinámica para el agente de log en BigQuery."""
    template = """Eres un agente encargado de registrar los resultados de la auditoría de código en BigQuery.
    De los metadatos extraidos obten el script_name ("Desconocido" si no hay nada), medallion_layer("Desconocido" por default), user_id ("Desconocido" si no se menciona), destination_tables (Si es una lista, toma el primer resultado. Si no hay nada usa "Desconocida")

DATOS EXTRAÍDOS:
- Script: {script_name}
- Capa: {medallion_layer}
- Autor: {user_id}
- Proyecto destino: {destination_tables}

1. LLama a la herramienta 'save_analysis_to_gcs' para salvar todos los análisis anteriores en un bucket de google cloud storage. No necesitas ingresar parametros.
2. Llama a la herramienta `save_review_to_bigquery` con estos parámetros exactos.
"""
    return await instructions_utils.inject_session_state(template, context)

bigquery_logger_agent = Agent(
    name="BigQueryLogger",
    model=config.worker_model,
    description="Registra los resultados de la revisión en BigQuery y devuelve el feedback final.",
    instruction=bigquery_logger_instruction_provider,
    tools=[FunctionTool(func=save_analysis_to_gcs), FunctionTool(func=save_review_to_bigquery)],
    output_key="final_feedback_delivered"
)

 