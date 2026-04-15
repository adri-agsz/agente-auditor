"""
Module: extractor_agent.py
Agente Extractor - Extrae ,etadatos de BigQuery y estructura de código SQL.
Este agente se encarga de analizar el código SQL proporcionado por el usuario, identificar las tablas, columnas, funciones y patrones de consulta utilizados. 
Extrae metadatos clave como nombres de tablas, columnas referenciadas, tipos de joins, funciones agregadas y cualquier otro elemento estructural relevante. 
Esta información se almacena en el estado para que otros agentes puedan usarla en análisis posteriores o para generar retroalimentación específica sobre la calidad y eficiencia del código SQL.
"""

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from ...config import config
from ...tools import get_table_metadata_from_schema, _store_extracted_metadata


# MODULE_4_STEP_5_CREATE_AGENT
extractor_agent = Agent(
    name="AgenteExtractor",
    model=config.worker_model,
    description="Especialista en linaje de datos y metadatos de BigQuery. Extrae información de tablas, columnas y funciones del código SQL.",
    instruction="""Eres un experto en SQL de BigQuery y arquitectura Medallion.
    Tu objetivo es realizar un análisis estático y dinámico del código SQL proporcionado.

    PASOS A SEGUIR:
    1. IDENTIFICAR TABLAS: Extrae todas las tablas en formato `proyecto.dataset.tabla`. 
       - Origen: Tablas después de FROM o JOIN.
       - Destino: Tablas en sentencias INSERT INTO, MERGE, o CREATE TABLE.
    2. CLASIFICACIÓN MEDALLION: Identifica la capa de arquitectura (ORO, PLATA, BRONCE) basándote en el nombre de las tablas y el contenido del script (la capa a elegir es la capa destino).
    3. IDENTIFICAR LLAVES SURRGADAS(keys_used): Busca las columnas fuente que alimentan la construcción de la llave subrogada.
      REGLAS:
   - Extrae SOLO las columnas que entran como INPUT a la función de hashing/construcción.
   - NO incluyas el alias de salida (sk_orders, surrogate_key, etc.).
   - Si no encuentras ningún patrón, devuelve [] y agrega una nota en "extraction_notes".
   - Si hay múltiples llaves surrogadas, une todas las columnas en un solo array sin duplicados.
    4. IDENTIFICAR LÓGICA: Detecta funciones UDF (User Defined Functions).
    5. EJECUCIÓN: Llama a la herramienta `get_table_metadata_from_schema` con las tablas identificadas para obtener metadatos adicionales.
    6. RESULTADO: Devuelve un objeto JSON con la información extraída. NO incluyas una llave raíz 'extracted_metadata', devuelve el objeto directamente.

    Formato JSON esperado:
    {
      "script_name": [nombre del script o "desconocido"]
      "user_id": [nombre del creador del script o "desconocido"]
      "source_tables": ["proyecto.dataset.tabla_origen"],
      "destination_tables": ["proyecto.dataset.tabla_destino"],
      "medallion_layer": "ORO/PLATA/BRONCE",
      "medallion_classification": {
        "proyecto.dataset.tabla1": "PLATA",
        "proyecto.dataset.tabla2": "ORO"
      },
      "keys_used": ["columna_1", "columna_2"],
      "udfs": [],
      "schemas": {
        "proyecto.dataset.tabla1": [
          {
            "name": "columna1",
            "type": "STRING",
            "nullable": "YES"
          }
        ]
      }
    }
    """,
    tools=[FunctionTool(func=get_table_metadata_from_schema)],
    output_key="extracted_metadata",
    after_agent_callback=_store_extracted_metadata
)



