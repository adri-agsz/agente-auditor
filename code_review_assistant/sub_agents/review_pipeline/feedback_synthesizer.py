"""
Feedback Synthesizer Agent - Provides comprehensive, personalized feedback.

This agent synthesizes all analysis results into constructive feedback,
incorporating past feedback history and tracking improvement over time.
"""

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import FunctionTool
from google.adk.utils import instructions_utils
from ...config import config
from ...tools import search_past_feedback, update_grading_progress, save_grading_report


import json

# MODULE_5_STEP_4_INSTRUCTION_PROVIDER
async def feedback_instruction_provider(context: ReadonlyContext) -> str:
    """Instrucción dinámica que inyecta varaibles de estado del contexto"""
    
    # 1. Extraer y limpiar extracted_metadata
    metadata_raw = context.state.get('extracted_metadata', {})
    metadata = metadata_raw
    
    if isinstance(metadata, str):
        cleaned = metadata.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[-1]
            cleaned = cleaned.rsplit('```', 1)[0]
        try:
            metadata = json.loads(cleaned.strip())
        except json.JSONDecodeError:
            pass

    if isinstance(metadata, dict) and 'extracted_metadata' in metadata:
        metadata = metadata['extracted_metadata']
        
    # 2. Extraer y limpiar analysis_summary
    analysis_raw = context.state.get('analysis_summary', "No se proporcionó un análisis previo.")
    analysis = analysis_raw
    
    if isinstance(analysis, str):
        cleaned = analysis.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[-1]
            cleaned = cleaned.rsplit('```', 1)[0]
        try:
            temp_analysis = json.loads(cleaned.strip())
            if isinstance(temp_analysis, dict) and 'analysis_summary' in temp_analysis:
                analysis = temp_analysis['analysis_summary']
            elif isinstance(temp_analysis, dict):
                # Si es un dict pero no tiene la llave esperada, lo volvemos a string formateado
                analysis = json.dumps(temp_analysis, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    elif isinstance(analysis, dict):
        if 'analysis_summary' in analysis:
            analysis = analysis['analysis_summary']
        else:
            analysis = json.dumps(analysis, indent=2, ensure_ascii=False)

    # Formatear metadata para el prompt
    if isinstance(metadata, dict):
        metadata_str = json.dumps(metadata, indent=2, ensure_ascii=False)
    else:
        metadata_str = str(metadata)

    # 3. Extraer el código original
    code_to_review = context.state.get('code_to_review', "No se proporcionó el código original.")

    # 4. Extraer el query de validación de unicidad
    uniqueness_query = context.state.get('uniqueness_validation_query', "No se pudo generar el query de validación de unicidad.")

    template = f"""Eres un data engineer expero en BigQuery y arquitectura Medallion. Analiza el script de transacción provisto.

## CONTEXTO DE AGENTES ANTERIORES:
Metadatos extraidos:
{metadata_str}

## SCRIPT A REVISAR:
{code_to_review}

## FORMATO DE RESPUESTA OBLIGATORIO
Responde EXCLUSIVAMENTE con estas secciones en este orden exacto.
No agregues texto adicional, saludos ni explicaciones fuera de las secciones.

## OBSERVACIONES DEL AUDITOR:
    -[Basado en tu conocimiento acerca de script de transacciones en una arquitectura medallion, genera una lista de riesgos que detectaste como experto,
   o NINGUNA si no hay nada relevante, con una pequeña explicación de los errores]

## INCONSISTENCIAS CON METADATOS:
  Valida EXCLUSIVAMENTE contra los schemas y tablas declarados arriba:
  - Columnas referenciadas en el script que NO existen en el schema fuente
  - Columnas del destino que el script NO popula (omisión)
  - Incompatibilidades de tipo (ej: STRING → INT64 sin CAST)
  - Columnas nullable=NO que podrían recibir NULL desde la fuente
   - O NINGUNA si no se detectan inconsistencias.

## SUGERENCIAS DE CORRECCIÓN (ACCIONABLE):
- Proporciona el bloque de código corregido EXACTO para cada error detectado.
- Usa el formato: "CAMBIAR: [bloque original] POR: [bloque nuevo]".
- Esto es vital para que Gemini CLI pueda aplicar el cambio automáticamente.

Guarda el resultado como texto en la variable de estado.
"""

    return template

# MODULE_5_STEP_4_SYNTHESIZER_AGENT
feedback_synthesizer_agent = Agent(
    name="FeedbackSynthesizer",
    model=config.worker_model,
    description="Analyze code inconsistencies and make other observations",
    instruction=feedback_instruction_provider,
    output_key="final_feedback"
)