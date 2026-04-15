"""
Tools for the Code Review Assistant.

These tools provide safe code analysis, style checking, test generation,
and feedback management capabilities using ADK's built-in code executor.
"""

import ast
import asyncio
import hashlib
import json
import os
import pycodestyle
import tempfile
import logging
from datetime import datetime
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
import re


from google.genai import types
from google.adk.tools import ToolContext

from google.cloud import bigquery
from google.cloud import storage
from google.oauth2 import service_account
import re

from .config import config
from .constants import StateKeys

# Configure logging
logger = logging.getLogger(__name__)

def _get_sa_credentials():
    """Carga las credenciales de la cuenta de servicio corporativa desde el archivo JSON."""
    try:
        # La ruta es relativa al archivo tools.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        key_path = os.path.join(current_dir, 'sa-datafusion-qa-key.json')

        if os.path.exists(key_path):
            logger.info(f"Cargando credenciales corporativas desde {key_path}")
            return service_account.Credentials.from_service_account_file(key_path)
        else:
            logger.warning(f"Archivo de credenciales no encontrado en {key_path}. Usando ADC.")
            return None
    except Exception as e:
        logger.error(f"Error cargando credenciales de cuenta de servicio: {e}")
        return None

async def save_analysis_to_gcs(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Saves the code analysis summary to a GCS bucket as an HTML file.
    """
    logger.info("Tool: Saving analysis report to GCS...")

    try:
        analysis_summary = tool_context.state.get("analysis_summary", "")
        final_summary = tool_context.state.get("final_feedback", "")

        if not analysis_summary and not final_summary:
            return {
                "status": "error",
                "message": "No hay contenido en analysis_summary ni final_feedback para guardar."
            }

        def md_to_html(text: str) -> str:
            if not text:
                return "<em>Sin contenido.</em>"
            import re

            # Headers
            text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
            text = re.sub(r'^## (.+)$',  r'<h2>\1</h2>', text, flags=re.MULTILINE)
            text = re.sub(r'^# (.+)$',   r'<h1>\1</h1>', text, flags=re.MULTILINE)

            # Negritas, itálicas, código inline
            text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<strong><em>\1</em></strong>', text)
            text = re.sub(r'\*\*(.*?)\*\*',     r'<strong>\1</strong>', text)
            text = re.sub(r'`([^`]+)`',          r'<code>\1</code>', text)

            # Bullets anidados (4+ espacios) ANTES que los de primer nivel
            text = re.sub(r'^ {4}[*\-]\s+(.+)$', r'<li class="nested">\1</li>', text, flags=re.MULTILINE)
            # Bullets de primer nivel: "* texto" o "- texto" con cualquier cantidad de espacios
            text = re.sub(r'^[*\-]\s+(.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)

            # Une líneas de continuación de un bullet al <li> anterior
            def merge_continuation(t):
                lines = t.split('\n')
                result = []
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith('<') and result:
                        last = result[-1]
                        if last.startswith('<li'):
                            result[-1] = last[:-5] + ' ' + stripped + '</li>'
                            continue
                    result.append(line)
                return '\n'.join(result)

            text = merge_continuation(text)

            # Anida <li class="nested"> dentro del <li> padre como sub-lista
            text = re.sub(
                r'(</li>)\n(<li class="nested">.*?</li>(?:\n<li class="nested">.*?</li>)*)',
                lambda m: m.group(1)[:-5] + '<ul class="sub">' + m.group(2) + '</ul></li>',
                text, flags=re.DOTALL
            )

            # Agrupa <li> consecutivos en <ul>
            text = re.sub(
                r'(<li>(?:(?!<li class="nested">)[\s\S])*?</li>\n?)+',
                lambda m: '<ul>' + m.group() + '</ul>',
                text
            )

            # Párrafos: bloques separados por línea vacía
            blocks = text.split('\n\n')
            result = []
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                if block.startswith('<'):
                    result.append(block)
                else:
                    result.append(f'<p>{block.replace(chr(10), " ")}</p>')

            return '\n'.join(result)

        timestamp_display = datetime.now().strftime("%d/%m/%Y %H:%M")
        timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")

        error_ratio = tool_context.state.get(StateKeys.ERROR_RATIO, "Desconocido")
        script = tool_context.state.get(StateKeys.SCRIPT_NAME, "Desconocido")
        capa = tool_context.state.get(StateKeys.MEDALLION_LAYER, "Desconocido")
        autor = tool_context.state.get(StateKeys.USER_ID, "Desconocido")

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reporte de Revisión de Código</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f5f5f0;
      color: #1a1a1a;
      padding: 2rem;
    }}
    .container {{ max-width: 860px; margin: 0 auto; }}
    header {{
      background: #fff;
      border: 0.5px solid #ddd;
      border-radius: 12px;
      padding: 1.5rem 2rem;
      margin-bottom: 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
    }}
    header h1 {{ font-size: 20px; font-weight: 500; color: #1a1a1a; }}
    header p {{ font-size: 13px; color: #888; margin-top: 4px; }}
    .badge {{
      font-size: 12px;
      background: #eeedfe;
      color: #3c3489;
      padding: 4px 12px;
      border-radius: 8px;
      font-weight: 500;
      white-space: nowrap;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 1.5rem;
    }}
    .meta-card {{
      background: #fff;
      border: 0.5px solid #ddd;
      border-radius: 8px;
      padding: 0.75rem 1rem;
    }}
    .meta-card .label {{ font-size: 12px; color: #888; margin-bottom: 4px; }}
    .meta-card .value {{ font-size: 14px; font-weight: 500; color: #1a1a1a; }}
    .section {{
      background: #fff;
      border: 0.5px solid #ddd;
      border-radius: 12px;
      padding: 1.5rem 2rem;
      margin-bottom: 1.5rem;
    }}
    .section h2 {{
      font-size: 15px;
      font-weight: 500;
      color: #1a1a1a;
      margin-bottom: 1rem;
      padding-bottom: 0.75rem;
      border-bottom: 0.5px solid #eee;
    }}
    .section-content {{ font-size: 14px; line-height: 1.7; color: #333; }}
    .section-content p {{ margin-bottom: 0.75rem; }}
    .section-content h3 {{ font-size: 14px; font-weight: 500; color: #1a1a1a; margin: 1.25rem 0 0.5rem; }}
    .section-content ul {{ padding-left: 1.25rem; margin: 0.4rem 0 0.75rem; }}
    .section-content ul.sub {{ margin-top: 6px; margin-bottom: 0; }}
    .section-content li {{ margin-bottom: 6px; line-height: 1.6; }}
    .section-content li.nested {{ color: #444; }}
    .section-content code {{
      font-family: 'SFMono-Regular', Consolas, monospace;
      font-size: 12px;
      background: #f0f0eb;
      padding: 2px 5px;
      border-radius: 4px;
    }}
    footer {{ text-align: center; font-size: 12px; color: #aaa; padding-top: 1rem; }}
  </style>
</head>
<body>
<div class="container">

  <header>
    <div>
      <h1>Reporte de revisiÃ³n de cÃ³digo</h1>
      <p>Generado el {timestamp_display}</p>
    </div>
    <span class="badge">Code Review Assistant</span>
  </header>

  <div class="meta-grid">
    <div class="meta-card"><div class="label">Script</div><div class="value">{script}</div></div>
    <div class="meta-card"><div class="label">Capa Medallion</div><div class="value">{capa}</div></div>
    <div class="meta-card"><div class="label">Autor</div><div class="value">{autor}</div></div>
    <div class="meta-card"><div class="label">Fecha revisiÃ³n</div><div class="value">{timestamp_display}</div></div>
    <div class="meta-card"><div class="label">Porcentaje de error</div><div class="value">{error_ratio}</div></div>
  </div>

  <div class="section">
    <h2>AnÃ¡lisis estructural</h2>
    <div class="section-content">{md_to_html(analysis_summary)}</div>
  </div>

  <div class="section">
    <h2>Feedback final y recomendaciones</h2>
    <div class="section-content">{md_to_html(final_summary)}</div>
  </div>

  <footer>Reporte generado automÃ¡ticamente por Code Review Assistant</footer>
</div>
</body>
</html>"""

        bucket_name = config.artifact_bucket or "scripts-transacciones-referencia-agente"
        if not bucket_name:
            return {
                "status": "error",
                "message": "Artifact bucket not configured in config.artifact_bucket"
            }

        filename = f"analysis_report_{timestamp_file}.html"

        credentials = _get_sa_credentials()
        client = storage.Client(project=config.google_cloud_project, credentials=credentials)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(filename)

        blob.upload_from_string(html_content, content_type='text/html')


        gcs_uri = f"https://storage.cloud.google.com/{bucket_name}/{filename}"
        logger.info(f"Tool: Analysis saved to {gcs_uri}")
        tool_context.state[StateKeys.ROUTE] = gcs_uri

        return {
            "status": "success",
            "artifact_saved": True,
            "filename": filename,
            "gcs_uri": gcs_uri,
            "summary": f"Analysis report saved to GCS as {filename}"
        }

    except Exception as e:
        error_msg = f"Failed to save analysis to GCS: {str(e)}"
        logger.error(f"Tool: {error_msg}", exc_info=True)
        return {
            "status": "error",
            "message": error_msg
        }

async def save_error_metrics(error_ratio: int, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Saves the error metrics as state context for other agents to use.

    Args:
        error_ratio: the ratio of correct points in the checklist / total points in checklist 
    Returns:
        Dictionary containing save status and details
    """
    logger.info("Tool: Saving analysis report to GCS...")

    try:
        if not error_ratio:
            return {
                "status": "error",
                "message": "No analysis text provided to save."
            }

        tool_context.state[StateKeys.ERROR_RATIO] = error_ratio

        return {
            "status": "success",
            "summary": f"Variable saved succesfully"
        }

    except Exception as e:
        error_msg = f"Failed to save variable error_ratio: {str(e)}"
        logger.error(f"Tool: {error_msg}", exc_info=True)
        return {
            "status": "error",
            "message": error_msg
        }

async def extract_metadata_from_sql(sql_code: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Extrae metadatos de tablas de BigQuery haciendo consultas 
    Args:
        sql_code: CÃ³digo SQL a analizar
        tool_context: Contexto de la herramienta para acceder al estado
    Returns:
        Diccionario con metadatos extraÃ­dos
    """
    logger.info("Tool: Extracting metadata from SQL code...")

    try:
        # Validar entrada
        if not sql_code or not isinstance(sql_code, str):
            return {
                "status": "error",
                "message": "No SQL code provided or invalid input"
            }

        # AnÃ¡lisis de texto para extraer metadatos clave
        metadata = {
            "tables": [],
            "columns": [],
            "functions": [],
            "joins": [],
            "medallion_layer": None,
            "execution_environment": None
        }

        # Extraer nombres de tablas (simplificado)
        for line in sql_code.splitlines():
            line = line.strip().lower()
            if line.startswith("from ") or line.startswith("join "):
                parts = line.split()
                if len(parts) >= 2:
                    table_name = parts[1].split('.')[0]  # Get base table name
                    metadata["tables"].append(table_name)

        # Determinar capa de arquitectura Medallion (simplificado)
        if 'bronze' in sql_code.lower():
            metadata["medallion_layer"] = 'BRONCE'
        elif 'silver' in sql_code.lower():
            metadata["medallion_layer"] = 'PLATA'
        elif 'gold' in sql_code.lower():
            metadata["medallion_layer"] = 'ORO'

        # Determinar ambiente de ejecuciÃ³n (simplificado)
        if 'habc-proj-' in sql_code.lower():
            metadata["execution_environment"] = 'habc-proj'

        # Almacenar metadatos en estado para otros agentes
        tool_context.state[StateKeys.SQL_METADATA] = metadata

        logger.info(f"Tool: Metadata extraction complete - Found {len(metadata['tables'])} tables")

        return {
            "status": "success",
            "metadata": metadata,
            "summary": f"Extracted metadata for {len(metadata['tables'])} tables and "
                       f"identified layer: {metadata['medallion_layer']}"
        }

    except Exception as e:
        error_msg = f"Metadata extraction failed: {str(e)}"
        logger.error(f"Tool: {error_msg}", exc_info=True)

        return {
            "status": "error",
            "message": error_msg
        }


async def get_table_metadata_from_schema(code: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Identifica tablas en el SQL y extrae su esquema real desde INFORMATION_SCHEMA sin ejecutar el cÃ³digo SQL.
    """
    logger.info("Tool: Extrayendo metadata de tablas...")
    try:
        # Validate input
        if not code or not isinstance(code, str):
            return {
                "status": "error",
                "message": "No code provided or invalid input"
            }

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            metadata = await loop.run_in_executor(executor, _extract_metadata_from_sql, code)

        tool_context.state[StateKeys.CODE_TO_REVIEW] = code
        tool_context.state[StateKeys.TABLE_METADATA] = metadata
        #tool_context.state[StateKeys.PROJECT_ID] = project_id

        logger.info(f"Tool: Metadata extraction complete - Found metadata for {len(metadata)} tables")

    except Exception as e:        
        logger.error(f"Tool: Error general al extraer metadata: {str(e)}", exc_info=True)     
        tool_context.state[StateKeys.CODE_TO_REVIEW] = code
        error_msg = f"Error al extraer metadatos: {str(e)}"
        logger.error(f"Tool: {error_msg}", exc_info=True)

        return {
            "status": "error",
            "message": error_msg
        }

    return metadata

def _parse_extracted_metadata(raw: str | dict) -> dict:
    """Limpia el markdown y parsea el JSON."""
    if isinstance(raw, dict):
        return raw  # ya estÃ¡ deserializado, nada que hacer

    # Elimina bloques ```json ... ``` o ``` ... ```
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = cleaned.replace("```", "").strip()

    return json.loads(cleaned)


def _store_extracted_metadata(
    callback_context: CallbackContext
) ->  None:
    raw = callback_context.state.get("extracted_metadata")
    if not raw:
        return None

    try:
        metadata = _parse_extracted_metadata(raw)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"âš ï¸  Error parseando extracted_metadata: {e}")
        return None

    callback_context.state[StateKeys.SCRIPT_NAME]        = metadata.get("script_name", [])
    callback_context.state[StateKeys.SOURCE_TABLES]      = metadata.get("source_tables", [])
    callback_context.state[StateKeys.DESTINATION_TABLES] = metadata.get("destination_tables", [])
    callback_context.state[StateKeys.MEDALLION_LAYER]    = metadata.get("medallion_layer")
    callback_context.state[StateKeys.USER_ID] = metadata.get("user_id", [])
    callback_context.state[StateKeys.MEDALLION_CLASS]    = metadata.get("medallion_classification", {})
    callback_context.state[StateKeys.KEYS_USED]          = metadata.get("keys_used", [])
    callback_context.state[StateKeys.UDFS]               = metadata.get("udfs", [])
    callback_context.state[StateKeys.SCHEMAS]            = metadata.get("schemas", {})

    return None

async def analyze_code_structure(code: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Analyzes Python code structure using AST parsing.

    This tool parses Python code to extract structural information
    including functions, classes, imports, and complexity metrics.

    Args:
        code: Python source code to analyze
        tool_context: ADK tool context for state management

    Returns:
        Dictionary containing analysis results and status
    """
    logger.info("Tool: Analyzing code structure...")

    try:
        # Validate input
        if not code or not isinstance(code, str):
            return {
                "status": "error",
                "message": "No code provided or invalid input"
            }

        # MODULE_4_STEP_3_ADD_ASYNC
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            tree = await loop.run_in_executor(executor, ast.parse, code)

            # MODULE_4_STEP_4_EXTRACT_DETAILS
            # Extract comprehensive structural information
            analysis = await loop.run_in_executor(
                executor, _extract_code_structure, tree, code
            )

        # MODULE_4_STEP_2_ADD_STATE_STORAGE
                # Store code and analysis for other agents to access
        tool_context.state[StateKeys.CODE_TO_REVIEW] = code
        tool_context.state[StateKeys.CODE_ANALYSIS] = analysis
        tool_context.state[StateKeys.CODE_LINE_COUNT] = len(code.splitlines())

        logger.info(f"Tool: Analysis complete - {analysis['metrics']['function_count']} functions, "
                    f"{analysis['metrics']['class_count']} classes")

        return {
            "status": "success",
            "analysis": analysis,
            "summary": f"Found {analysis['metrics']['function_count']} functions and "
                       f"{analysis['metrics']['class_count']} classes"
        }

    except SyntaxError as e:
        error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
        logger.error(f"Tool: {error_msg}")
        tool_context.state[StateKeys.CODE_TO_REVIEW] = code
        tool_context.state[StateKeys.SYNTAX_ERROR] = error_msg

        return {
            "status": "error",
            "error_type": "syntax",
            "message": error_msg,
            "line": e.lineno,
            "offset": e.offset
        }

    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        logger.error(f"Tool: {error_msg}", exc_info=True)
        tool_context.state[StateKeys.CODE_TO_REVIEW] = code

        return {
            "status": "error",
            "error_type": "parse",
            "message": error_msg
        }



## -- FUNCIONES AUXILIARES --

def _extract_metadata_from_sql(code: str) -> Dict[str, Any]:
    """
    FunciÃ³n auxiliar para extraer metadatos de tablas desde BigQuery.
    """
    try:
        # Inicializar el cliente de BigQuery. Se asume que las credenciales estÃ¡n configuradas 
        # en el ambiente (Application Default Credentials).

        ### PROJECT_ID HARCODEADO PARA PRUEBAS - DEBERÃA VENIR DEL ESTADO O CONTEXTO
        project_id = config.google_cloud_project or "habc-proj-dlh-qa"  # Usar configuración o fallback
        credentials = _get_sa_credentials()
        client = bigquery.Client(project=project_id, credentials=credentials)
    except Exception as e:
        logger.error(f"Error al inicializar el cliente de BigQuery: {str(e)}")
        return {"error": f"No se pudo inicializar el cliente de BigQuery: {str(e)}"}

    # 2. Extraer nombres de tablas usando Regex (Busca patrones `dataset.tabla` o `proyecto.dataset.tabla`)
    table_pattern = r'`?([a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+|[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)`?'
    found_tables = list(set(re.findall(table_pattern, code)))

    all_metadata = {}

    for full_table_name in found_tables:
        # Limpiar y dividir el nombre de la tabla
        parts = full_table_name.replace('`', '').split('.')

        if len(parts) == 3:
            proj, dataset, table = parts
        elif len(parts) == 2:
            proj, dataset, table = project_id, parts[0], parts[1]
        else:
            continue

        logger.info(f"Consultando metadatos para: {dataset}.{table}...")

        # 3. Consulta a INFORMATION_SCHEMA.COLUMNS para obtener el esquema real
        query = f"""
        SELECT
            column_name,
            data_type,
            is_nullable
        FROM `{proj}.{dataset}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = '{table}'
        ORDER BY ordinal_position;
        """

        try:
            query_job = client.query(query)
            columns = []
            for row in query_job.result():
                columns.append({
                    "name": row.column_name,
                    "type": row.data_type,
                    "nullable": row.is_nullable
                })

            all_metadata[full_table_name] = columns
        except Exception as e:
            logger.warning(f"Tool: Error al consultar metadatos para la tabla {full_table_name}: {str(e)}")
            all_metadata[full_table_name] = f"Error: No se pudo acceder: {str(e)}"

    return all_metadata

# MODULE_4_STEP_4_HELPER_FUNCTION
def _extract_code_structure(tree: ast.AST, code: str) -> Dict[str, Any]:
    """
    Helper function to extract structural information from AST.
    Runs in thread pool for CPU-bound work.
    """
    functions = []
    classes = []
    imports = []
    docstrings = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_info = {
                'name': node.name,
                'args': [arg.arg for arg in node.args.args],
                'lineno': node.lineno,
                'has_docstring': ast.get_docstring(node) is not None,
                'is_async': isinstance(node, ast.AsyncFunctionDef),
                'decorators': [d.id for d in node.decorator_list
                               if isinstance(d, ast.Name)]
            }
            functions.append(func_info)

            if func_info['has_docstring']:
                docstrings.append(f"{node.name}: {ast.get_docstring(node)[:50]}...")

        elif isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(item.name)

            class_info = {
                'name': node.name,
                'lineno': node.lineno,
                'methods': methods,
                'has_docstring': ast.get_docstring(node) is not None,
                'base_classes': [base.id for base in node.bases
                                 if isinstance(base, ast.Name)]
            }
            classes.append(class_info)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    'module': alias.name,
                    'alias': alias.asname,
                    'type': 'import'
                })
        elif isinstance(node, ast.ImportFrom):
            imports.append({
                'module': node.module or '',
                'names': [alias.name for alias in node.names],
                'type': 'from_import',
                'level': node.level
            })

    return {
        'functions': functions,
        'classes': classes,
        'imports': imports,
        'docstrings': docstrings,
        'metrics': {
            'line_count': len(code.splitlines()),
            'function_count': len(functions),
            'class_count': len(classes),
            'import_count': len(imports),
            'has_main': any(f['name'] == 'main' for f in functions),
            'has_if_main': '__main__' in code,
            'avg_function_length': _calculate_avg_function_length(tree)
        }
    }


def _calculate_avg_function_length(tree: ast.AST) -> float:
    """Calculate average function length in lines."""
    function_lengths = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                length = node.end_lineno - node.lineno + 1
                function_lengths.append(length)

    if function_lengths:
        return sum(function_lengths) / len(function_lengths)
    return 0.0

# MODULE_5_STEP_1_STYLE_CHECKER_TOOL
async def check_code_style(code: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Checks code style compliance using pycodestyle (PEP 8).

    Args:
        code: Python source code to check (or will retrieve from state)
        tool_context: ADK tool context

    Returns:
        Dictionary containing style score and issues
    """
    logger.info("Tool: Checking code style...")

    try:
        # Retrieve code from state if not provided
        if not code:
            code = tool_context.state.get(StateKeys.CODE_TO_REVIEW, '')
            if not code:
                return {
                    "status": "error",
                    "message": "No code provided or found in state"
                }

        # Run style check in thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor, _perform_style_check, code
            )

        # Store results in state
        tool_context.state[StateKeys.STYLE_SCORE] = result['score']
        tool_context.state[StateKeys.STYLE_ISSUES] = result['issues']
        tool_context.state[StateKeys.STYLE_ISSUE_COUNT] = result['issue_count']

        logger.info(f"Tool: Style check complete - Score: {result['score']}/100, "
                    f"Issues: {result['issue_count']}")

        return result

    except Exception as e:
        error_msg = f"Style check failed: {str(e)}"
        logger.error(f"Tool: {error_msg}", exc_info=True)

        # Set default values on error
        tool_context.state[StateKeys.STYLE_SCORE] = 0
        tool_context.state[StateKeys.STYLE_ISSUES] = []

        return {
            "status": "error",
            "message": error_msg,
            "score": 0
        }

# MODULE_5_STEP_1_STYLE_HELPERS
def _perform_style_check(code: str) -> Dict[str, Any]:
    """Helper to perform style check in thread pool."""
    import io
    import sys

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        # Capture stdout to get pycodestyle output
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        style_guide = pycodestyle.StyleGuide(
            quiet=False,  # We want output
            max_line_length=100,
            ignore=['E501', 'W503']
        )

        result = style_guide.check_files([tmp_path])

        # Restore stdout
        sys.stdout = old_stdout

        # Parse captured output
        output = captured_output.getvalue()
        issues = []

        for line in output.strip().split('\n'):
            if line and ':' in line:
                parts = line.split(':', 4)
                if len(parts) >= 4:
                    try:
                        issues.append({
                            'line': int(parts[1]),
                            'column': int(parts[2]),
                            'code': parts[3].split()[0] if len(parts) > 3 else 'E000',
                            'message': parts[3].strip() if len(parts) > 3 else 'Unknown error'
                        })
                    except (ValueError, IndexError):
                        pass

        # Add naming convention checks
        try:
            tree = ast.parse(code)
            naming_issues = _check_naming_conventions(tree)
            issues.extend(naming_issues)
        except SyntaxError:
            pass  # Syntax errors will be caught elsewhere

        # Calculate weighted score
        score = _calculate_style_score(issues)

        return {
            "status": "success",
            "score": score,
            "issue_count": len(issues),
            "issues": issues[:10],  # First 10 issues
            "summary": f"Style score: {score}/100 with {len(issues)} violations"
        }

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _check_naming_conventions(tree: ast.AST) -> List[Dict[str, Any]]:
    """Check PEP 8 naming conventions."""
    naming_issues = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Skip private/protected methods and __main__
            if not node.name.startswith('_') and node.name != node.name.lower():
                naming_issues.append({
                    'line': node.lineno,
                    'column': node.col_offset,
                    'code': 'N802',
                    'message': f"N802 function name '{node.name}' should be lowercase"
                })
        elif isinstance(node, ast.ClassDef):
            # Check if class name follows CapWords convention
            if not node.name[0].isupper() or '_' in node.name:
                naming_issues.append({
                    'line': node.lineno,
                    'column': node.col_offset,
                    'code': 'N801',
                    'message': f"N801 class name '{node.name}' should use CapWords convention"
                })

    return naming_issues


def _calculate_style_score(issues: List[Dict[str, Any]]) -> int:
    """Calculate weighted style score based on violation severity."""
    if not issues:
        return 100

    # Define weights by error type
    weights = {
        'E1': 10,  # Indentation errors
        'E2': 3,  # Whitespace errors
        'E3': 5,  # Blank line errors
        'E4': 8,  # Import errors
        'E5': 5,  # Line length
        'E7': 7,  # Statement errors
        'E9': 10,  # Syntax errors
        'W2': 2,  # Whitespace warnings
        'W3': 2,  # Blank line warnings
        'W5': 3,  # Line break warnings
        'N8': 7,  # Naming conventions
    }

    total_deduction = 0
    for issue in issues:
        code_prefix = issue['code'][:2] if len(issue['code']) >= 2 else 'E2'
        weight = weights.get(code_prefix, 3)
        total_deduction += weight

    # Cap at 100 points deduction
    return max(0, 100 - min(total_deduction, 100))

# MODULE_5_STEP_4_SEARCH_PAST_FEEDBACK
async def search_past_feedback(developer_id: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Search for past feedback in memory service.

    Args:
        developer_id: ID of the developer (defaults to "default_user")
        tool_context: ADK tool context with potential memory service access

    Returns:
        Dictionary containing feedback search results
    """
    logger.info(f"Tool: Searching for past feedback for developer {developer_id}...")

    try:
        # Default developer ID if not provided
        if not developer_id:
            developer_id = tool_context.state.get(StateKeys.USER_ID, 'default_user')

        # Check if memory service is available
        if hasattr(tool_context, 'search_memory'):
            try:
                # Perform structured searches
                queries = [
                    f"developer:{developer_id} code review feedback",
                    f"developer:{developer_id} common issues",
                    f"developer:{developer_id} improvements"
                ]

                all_feedback = []
                patterns = {
                    'common_issues': [],
                    'improvements': [],
                    'strengths': []
                }

                for query in queries:
                    search_result = await tool_context.search_memory(query)

                    if search_result and hasattr(search_result, 'memories'):
                        for memory in search_result.memories[:5]:
                            memory_text = memory.text if hasattr(memory, 'text') else str(memory)
                            all_feedback.append(memory_text)

                            # Extract patterns
                            if 'style' in memory_text.lower():
                                patterns['common_issues'].append('style compliance')
                            if 'improved' in memory_text.lower():
                                patterns['improvements'].append('showing improvement')
                            if 'excellent' in memory_text.lower():
                                patterns['strengths'].append('consistent quality')

                # Store in state
                tool_context.state[StateKeys.PAST_FEEDBACK] = all_feedback
                tool_context.state[StateKeys.FEEDBACK_PATTERNS] = patterns

                logger.info(f"Tool: Found {len(all_feedback)} past feedback items")

                return {
                    "status": "success",
                    "feedback_found": True,
                    "count": len(all_feedback),
                    "summary": " | ".join(all_feedback[:3]) if all_feedback else "No feedback",
                    "patterns": patterns
                }

            except Exception as e:
                logger.warning(f"Tool: Memory search error: {e}")

        # Fallback: Check state for cached feedback
        cached_feedback = tool_context.state.get(StateKeys.USER_PAST_FEEDBACK_CACHE, [])
        if cached_feedback:
            tool_context.state[StateKeys.PAST_FEEDBACK] = cached_feedback
            return {
                "status": "success",
                "feedback_found": True,
                "count": len(cached_feedback),
                "summary": "Using cached feedback",
                "patterns": {}
            }

        # No feedback found
        tool_context.state[StateKeys.PAST_FEEDBACK] = []
        logger.info("Tool: No past feedback found")

        return {
            "status": "success",
            "feedback_found": False,
            "message": "No past feedback available - this appears to be a first submission",
            "patterns": {}
        }

    except Exception as e:
        error_msg = f"Feedback search error: {str(e)}"
        logger.error(f"Tool: {error_msg}", exc_info=True)

        tool_context.state[StateKeys.PAST_FEEDBACK] = []

        return {
            "status": "error",
            "message": error_msg,
            "feedback_found": False
        }

# MODULE_5_STEP_4_UPDATE_GRADING_PROGRESS
async def update_grading_progress(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Updates grading progress counters and metrics in state.
    """
    logger.info("Tool: Updating grading progress...")

    try:
        current_time = datetime.now().isoformat()

        # Build all state changes
        state_updates = {}

        # Temporary (invocation-level) state
        state_updates[StateKeys.TEMP_PROCESSING_TIMESTAMP] = current_time

        # Session-level state
        attempts = tool_context.state.get(StateKeys.GRADING_ATTEMPTS, 0) + 1
        state_updates[StateKeys.GRADING_ATTEMPTS] = attempts
        state_updates[StateKeys.LAST_GRADING_TIME] = current_time

        # User-level persistent state
        lifetime_submissions = tool_context.state.get(StateKeys.USER_TOTAL_SUBMISSIONS, 0) + 1
        state_updates[StateKeys.USER_TOTAL_SUBMISSIONS] = lifetime_submissions
        state_updates[StateKeys.USER_LAST_SUBMISSION_TIME] = current_time

        # Calculate improvement metrics
        current_style_score = tool_context.state.get(StateKeys.STYLE_SCORE, 0)
        last_style_score = tool_context.state.get(StateKeys.USER_LAST_STYLE_SCORE, 0)
        score_improvement = current_style_score - last_style_score

        state_updates[StateKeys.USER_LAST_STYLE_SCORE] = current_style_score
        state_updates[StateKeys.SCORE_IMPROVEMENT] = score_improvement

        # Track test results if available
        test_results = tool_context.state.get(StateKeys.TEST_EXECUTION_SUMMARY, {})

        # Parse if it's a string
        if isinstance(test_results, str):
            try:
                test_results = json.loads(test_results)
            except:
                test_results = {}

        if test_results and test_results.get('test_summary', {}).get('total_tests_run', 0) > 0:
            summary = test_results['test_summary']
            total = summary.get('total_tests_run', 0)
            passed = summary.get('tests_passed', 0)
            if total > 0:
                pass_rate = (passed / total) * 100
                state_updates[StateKeys.USER_LAST_TEST_PASS_RATE] = pass_rate

        # Apply all updates atomically
        for key, value in state_updates.items():
            tool_context.state[key] = value

        logger.info(f"Tool: Progress updated - Attempt #{attempts}, "
                    f"Lifetime: {lifetime_submissions}")

        return {
            "status": "success",
            "session_attempts": attempts,
            "lifetime_submissions": lifetime_submissions,
            "timestamp": current_time,
            "improvement": {
                "style_score_change": score_improvement,
                "direction": "improved" if score_improvement > 0 else "declined"
            },
            "summary": f"Attempt #{attempts} recorded, {lifetime_submissions} total submissions"
        }

    except Exception as e:
        error_msg = f"Progress update error: {str(e)}"
        logger.error(f"Tool: {error_msg}", exc_info=True)

        return {
            "status": "error",
            "message": error_msg
        }

# MODULE_5_STEP_4_SAVE_GRADING_REPORT
async def save_grading_report(feedback_text: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Saves a detailed grading report as an artifact.

    Args:
        feedback_text: The feedback text to include in the report
        tool_context: ADK tool context for state management

    Returns:
        Dictionary containing save status and details
    """
    logger.info("Tool: Saving grading report...")

    try:
        # Gather all relevant data from state
        code = tool_context.state.get(StateKeys.CODE_TO_REVIEW, '')
        analysis = tool_context.state.get(StateKeys.CODE_ANALYSIS, {})
        style_score = tool_context.state.get(StateKeys.STYLE_SCORE, 0)
        style_issues = tool_context.state.get(StateKeys.STYLE_ISSUES, [])

        # Get test results
        test_results = tool_context.state.get(StateKeys.TEST_EXECUTION_SUMMARY, {})

        # Parse if it's a string
        if isinstance(test_results, str):
            try:
                test_results = json.loads(test_results)
            except:
                test_results = {}

        timestamp = datetime.now().isoformat()

        # Create comprehensive report dictionary
        report = {
            'timestamp': timestamp,
            'grading_attempt': tool_context.state.get(StateKeys.GRADING_ATTEMPTS, 1),
            'code': {
                'content': code,
                'line_count': len(code.splitlines()),
                'hash': hashlib.md5(code.encode()).hexdigest()
            },
            'analysis': analysis,
            'style': {
                'score': style_score,
                'issues': style_issues[:5]  # First 5 issues
            },
            'tests': test_results,
            'feedback': feedback_text,
            'improvements': {
                'score_change': tool_context.state.get(StateKeys.SCORE_IMPROVEMENT, 0),
                'from_last_score': tool_context.state.get(StateKeys.USER_LAST_STYLE_SCORE, 0)
            }
        }

        # Convert report to JSON string
        report_json = json.dumps(report, indent=2)
        report_part = types.Part.from_text(text=report_json)

        # Try to save as artifact if the service is available
        if hasattr(tool_context, 'save_artifact'):
            try:
                # Generate filename with timestamp (replace colons for filesystem compatibility)
                filename = f"grading_report_{timestamp.replace(':', '-')}.json"

                # Save the main report
                version = await tool_context.save_artifact(filename, report_part)

                # Also save a "latest" version for easy access
                await tool_context.save_artifact("latest_grading_report.json", report_part)

                logger.info(f"Tool: Report saved as {filename} (version {version})")

                # Store report in state as well for redundancy
                tool_context.state[StateKeys.USER_LAST_GRADING_REPORT] = report

                return {
                    "status": "success",
                    "artifact_saved": True,
                    "filename": filename,
                    "version": str(version),
                    "size": len(report_json),
                    "summary": f"Report saved as {filename}"
                }

            except Exception as artifact_error:
                logger.warning(f"Artifact service error: {artifact_error}, falling back to state storage")
                # Continue to fallback below

        # Fallback: Store in state if artifact service is not available or failed
        tool_context.state[StateKeys.USER_LAST_GRADING_REPORT] = report
        logger.info("Tool: Report saved to state (artifact service not available)")

        return {
            "status": "success",
            "artifact_saved": False,
            "message": "Report saved to state only",
            "size": len(report_json),
            "summary": "Report saved to session state"
        }

    except Exception as e:
        error_msg = f"Report save error: {str(e)}"
        logger.error(f"Tool: {error_msg}", exc_info=True)

        # Still try to save minimal data to state
        try:
            tool_context.state[StateKeys.USER_LAST_GRADING_REPORT] = {
                'error': error_msg,
                'feedback': feedback_text,
                'timestamp': datetime.now().isoformat()
            }
        except:
            pass

        return {
            "status": "error",
            "message": error_msg,
            "artifact_saved": False,
            "summary": f"Failed to save report: {error_msg}"
        }

# MODULE_6_STEP_3_VALIDATE_FIXED_STYLE


# MODULE_6_STEP_3_COMPILE_FIX_REPORT


# MODULE_6_STEP_3_EXIT_FIX_LOOP
def extract_and_save_error_metrics(callback_context: CallbackContext) -> None:
    """
    Calcula métricas basándose exclusivamente en emojis (❌, ⚠️, ✅).
    """
    analysis_text = callback_context.state.get("analysis_summary", "")
    
    # Definimos los disparadores visuales
    # Usamos constantes para facilitar el mantenimiento
    EMOJI_ERROR = "❌"
    EMOJI_WARN  = "⚠️"
    EMOJI_OK    = "✅"

    # Contadores iniciales
    counts = {"error": 0, "warn": 0, "ok": 0}

    # Procesar línea por línea para evitar contar múltiples emojis en una sola línea 
    # (si esa es la lógica que prefieres conservar)
    for line in analysis_text.splitlines():
        if EMOJI_ERROR in line:
            counts["error"] += 1
        elif EMOJI_WARN in line:
            counts["warn"] += 1
        elif EMOJI_OK in line:
            counts["ok"] += 1

    # Cálculo del porcentaje
    total = sum(counts.values())
    error_pct = round((counts["ok"] / total) * 100, 2) if total > 0 else 0.0

    # Guardar en el estado
    callback_context.state[StateKeys.ERROR_RATIO] = error_pct

    return None

# MODULE_6_STEP_6_SAVE_FIX_REPORT


async def save_review_to_bigquery(
    script_name: str,
    medallion_layer: str,
    author: str,
    project_destination: str,
    tool_context: ToolContext
) -> Dict[str, Any]:
    """
    Guarda el resultado de la revisión en una tabla de BigQuery.

    Args:
        script_name: Nombre del script revisado.
        medallion_layer: Capa de arquitectura (BRONCE, PLATA, ORO).
        author: Autor del script.
        failed_rules_count: Conteo de reglas no cumplidas
        tool_context: Contexto de la herramienta.

    Returns:
        Diccionario con el estado de la operación.
    """
    logger.info(f"Tool: Guardando revisión en BigQuery para {script_name}...")

    try:
        project_id = config.google_cloud_project or "habc-proj-etl-qa"  # Usar configuración o fallback
        dataset_id = "tablas_temporales"
        table_id = "bitacora_scripts"
        
        if not project_id:
            return {"status": "error", "message": "GOOGLE_CLOUD_PROJECT no está configurado."}

        credentials = _get_sa_credentials(); client = bigquery.Client(project=project_id, credentials=credentials)
        table_ref = f"{project_id}.{dataset_id}.{table_id}"

        enlace = tool_context.state.get(StateKeys.ROUTE, "SIN RUTA")
        error_ratio = tool_context.state.get(StateKeys.ERROR_RATIO, "0")
        rows_to_insert = [
            {
                "fecha_ejecucion": datetime.now().isoformat(),
                "script": script_name,
                "proyecto": project_destination,
                "estatus": "RECHAZADO",
                "autor": author,
                "reglas": error_ratio,
                "enlace": enlace
               
            }
        ]

        errors = client.insert_rows_json(table_ref, rows_to_insert)

        if not errors:
            logger.info("Tool: Registro insertado exitosamente en BigQuery.")
            return {"status": "success", "message": "Registro guardado en BigQuery."}
        else:
            logger.error(f"Tool: Errores al insertar en BigQuery: {errors}")
            return {"status": "error", "message": f"Errores de BigQuery: {errors}"}

    except Exception as e:
        logger.error(f"Tool: Error al guardar en BigQuery: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}


def load_sql_from_gcs(
    bucket_name: str,
    file_name: str,
    tool_context: ToolContext,
) -> dict:

    if not file_name.lower().endswith(".sql"):
        return {"status": "error", "message": f"'{file_name}' no es un .sql."}

    try:
        credentials = _get_sa_credentials(); storage_client = storage.Client(project=config.google_cloud_project, credentials=credentials)
        sql_content    = storage_client.bucket(bucket_name).blob(file_name).download_as_text()

        if not sql_content.strip():
            return {"status": "error", "message": "El archivo SQL está vacío."}

        path_meta    = _parse_gcs_path(file_name)
        environment  = _infer_environment(bucket_name)
        layer_hint   = _infer_layer_from_folder(path_meta["layer_folder"])

        tool_context.state[StateKeys.CODE_TO_REVIEW]  = sql_content
        tool_context.state[StateKeys.FILE_NAME]        = file_name
        tool_context.state[StateKeys.SCRIPT_NAME]      = path_meta["script_name"]
        tool_context.state[StateKeys.BUCKET_NAME]      = bucket_name

        logger.info(
            f"Tool: gs://{bucket_name}/{file_name} | "
            f"env={environment} | layer={layer_hint} | "
            f"script={path_meta['script_name']}"
        )

        return {
            "status":       "success",
            "environment":  environment,
            "layer_hint":   layer_hint,
            "script_name":  path_meta["script_name"],
            "layer_folder": path_meta["layer_folder"],
            "gcs_uri":      f"gs://{bucket_name}/{file_name}",
            "sql_preview":  sql_content[:200] + "..." if len(sql_content) > 200 else sql_content,
        }

    except Exception as e:
        logger.error(f"Tool: Error leyendo GCS — {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

def _infer_environment(bucket_name: str) -> str:
    """
    Con un solo bucket orquestado, el ambiente se infiere
    por el nombre del bucket o se lee desde config directamente.
    """
    if bucket_name == "us-central1-habc-orquestado-82a883fd-bucket":
        return "qa"
    if bucket_name ==  "us-central1-habc-orquestado-07851463-bucket":
        return "prd"

    # Fallback heurístico
    name_lower = bucket_name.lower()
    if any(k in name_lower for k in ("prd", "prod")):
        return "prd"
    if any(k in name_lower for k in ("qa", "test", "dev", "staging", "orquestado")):
        return "qa"

    return "unknown"

def _parse_gcs_path(file_name: str) -> dict:
    """
    Descompone rutas como 'data/transaccion-sql-bronce/mi_script.sql'

    Retorna:
        folder_path:  "data/transaccion-sql-bronce"
        script_name:  "mi_script"
        layer_folder: "transaccion-sql-bronce"  ← útil para inferir capa Medallion
    """
    parts       = file_name.replace("\\", "/").split("/")
    script_name = parts[-1].replace(".sql", "")
    folder_path = "/".join(parts[:-1]) if len(parts) > 1 else ""
    layer_folder = parts[-2] if len(parts) >= 2 else ""

    return {
        "script_name":  script_name,
        "folder_path":  folder_path,
        "layer_folder": layer_folder,   # "transaccion-sql-bronce"
    }

def _infer_layer_from_folder(layer_folder: str) -> str:
    """
    Infiere la capa Medallion desde el nombre de la carpeta.
    Ejemplos:
      'transaccion-sql-bronce' → 'BRONCE'
      'clientes-sql-plata'     → 'PLATA'
      'reporte-sql-oro'        → 'ORO'
    """
    folder_lower = layer_folder.lower()
    if "oro" in folder_lower or "gold" in folder_lower:
        return "ORO"
    if "plata" in folder_lower or "silver" in folder_lower:
        return "PLATA"
    if "bronce" in folder_lower or "bronze" in folder_lower:
        return "BRONCE"
    return "BRONCE"  # default conservador

BUCKET_ENV_MAP: dict[str, str] = {
    "us-central1-habc-orquestado-82a883fd-bucket":  "qa",
    "us-central1-habc-orquestado-07851463-bucket": "prd",
}

# Module exports
__all__ = [
    'analyze_code_structure',
    'check_code_style',
    'search_past_feedback',
    'update_grading_progress',
    'save_grading_report',
    'save_review_to_bigquery',
    'save_analysis_to_gcs',
    'validate_fixed_style',
    'compile_fix_report',
    'save_fix_report',
    '_store_extracted_metadata'
]
