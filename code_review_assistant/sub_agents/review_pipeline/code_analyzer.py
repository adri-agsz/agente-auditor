"""
Code Analyzer Agent - Understands code structure and complexity.

This agent is responsible for parsing and analyzing Python code structure,
identifying functions, classes, imports, and potential issues.
"""

import os
import json
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from ...config import config
from google.adk.agents.readonly_context import ReadonlyContext
from ...tools import analyze_code_structure, save_analysis_to_gcs, save_error_metrics, extract_and_save_error_metrics
from google.adk.utils import instructions_utils
from ...constants import StateKeys

async def code_analyzer_instruction_provider(context: ReadonlyContext) -> str:
    """Instrucción dinámica que inyecta variables de estado para el análisis de código y carga criterios por capa."""
    
    raw = context.state.get('extracted_metadata', {})
    
    # 1. Si viene como string, limpiar backticks y parsear
    if isinstance(raw, str):
        # Eliminar fences de markdown ```json ... ```
        cleaned = raw.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[-1]  # quitar primera línea con ```json
            cleaned = cleaned.rsplit('```', 1)[0]  # quitar cierre ```
        try:
            raw = json.loads(cleaned.strip())
        except json.JSONDecodeError:
            raw = {}

    # 2. Resolver la anidación extra: {"extracted_metadata": {...}}
    if isinstance(raw, dict) and 'extracted_metadata' in raw:
        raw = raw['extracted_metadata']

    # 3. Ahora sí leer medallion_layer
    layer = raw.get('medallion_layer', 'BRONCE') if isinstance(raw, dict) else 'BRONCE'
    
    layer = str(layer).upper()
    layer if layer in ['ORO', 'PLATA', 'BRONCE'] else 'BRONCE'
        
    # Cargar el archivo de criterios correspondiente
    # Los archivos están en el directorio raíz de code_review_assistant
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    criteria_file = f"criterios_{layer.lower()}.md"
    criteria_path = os.path.join(base_dir, criteria_file)
    
    criteria_content = ""
    if os.path.exists(criteria_path):
        with open(criteria_path, 'r', encoding='utf-8') as f:
            criteria_content = f.read()
    else:
        criteria_content = f"Error: No se encontró el archivo de criterios para la capa {layer}."

    template = f"""Eres un revisor senior de scripts SQL para una arquitectura Medallion en BigQuery.
Analiza el siguiente script de CAPA {layer} contra los criterios definidos.

## SCRIPT A REVISAR:
{{code_to_review}}

## CRITERIOS DE REVISIÓN:
{criteria_content}


## INDICACIONES
- NO incluyas frases introductorias como "Aquí tienes el análisis".
- Cubre TODOS los criterios mencionados.
- Usa ✅ para criterios cumplidos, ⚠️ para cumplimiento parcial, ❌ para incumplimientos.
  Esto es importante — el sistema los usa para calcular métricas automáticamente.
- En caso de errores, da comentarios detallados con la explicación de los errores
- Guarda el resultado como texto en la variable de estado, sin anotaciones del tipo de dato que es el archivo.
"""

    return await instructions_utils.inject_session_state(template, context)

# MODULE_4_STEP_5_CREATE_AGENT
code_analyzer_agent = Agent(
    name="CodeAnalyzer",
    model="gemini-2.5-flash",
    description="Analyzes Python code structure and identifies components",
    instruction=code_analyzer_instruction_provider,
    output_key="analysis_summary",
    after_agent_callback=extract_and_save_error_metrics,
)



