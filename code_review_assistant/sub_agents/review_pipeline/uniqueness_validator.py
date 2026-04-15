"""
Uniqueness Validator Agent - Generates SQL to validate record uniqueness.

This agent is responsible for creating a BigQuery SQL query that checks if the 
keys used in a script result in unique records (no duplicates) in the destination table.
"""

import json
from google.adk.agents import Agent
from ...config import config
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.utils import instructions_utils

async def uniqueness_validator_instruction_provider(context: ReadonlyContext) -> str:
    """Dynamic instruction that uses extracted metadata to generate a uniqueness validation query."""
    
    metadata = context.state.get('extracted_metadata', {})
    
    # Clean and parse metadata if it's a string
    if isinstance(metadata, str):
        cleaned = metadata.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[-1]
            cleaned = cleaned.rsplit('```', 1)[0]
        try:
            metadata = json.loads(cleaned.strip())
        except json.JSONDecodeError:
            metadata = {}

    if isinstance(metadata, dict) and 'extracted_metadata' in metadata:
        metadata = metadata['extracted_metadata']

    keys_used = metadata.get('keys_used', [])
    destination_tables = metadata.get('destination_tables', [])
    
    keys_str = ", ".join(keys_used) if keys_used else "COLUMN_NAMES"
    table_str = destination_tables[0] if destination_tables else "PROJECT.DATASET.TABLE"

    template = f"""Eres un experto en BigQuery. Tu tarea es generar una consulta SQL para validar la unicidad de los registros en la tabla destino basándote en las llaves identificadas.

## CONTEXTO:
- **Tabla Destino:** {table_str}
- **Llaves Identificadas:** {keys_str}

## OBJETIVO:
Generar una consulta SQL que:
1. Agrupe por las llaves identificadas.
2. Identifique si hay más de un registro por cada combinación de llaves.
3. Devuelva las filas duplicadas (si existen) con el conteo de repeticiones.


## FORMATO DE RESPUESTA:
Devuelve ÚNICAMENTE el bloque de código SQL de BigQuery. No incluyas explicaciones adicionales fuera del bloque de código.

Ejemplo de estructura esperada:
```sql
SELECT
  {keys_str},
  COUNT(*) as duplicate_count
FROM
  `{table_str}`
GROUP BY
  {keys_str}
HAVING
  duplicate_count > 1
```

Si no se identificaron llaves o tablas, genera un template genérico indicando dónde completar la información.
"""
    return await instructions_utils.inject_session_state(template, context)

uniqueness_validator_agent = Agent(
    name="UniquenessValidator",
    model=config.worker_model,
    description="Genera consultas SQL para validar que no existan duplicados según las llaves del script.",
    instruction=uniqueness_validator_instruction_provider,
    output_key="uniqueness_validation_query"
)
