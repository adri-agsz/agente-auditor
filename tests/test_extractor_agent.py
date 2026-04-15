import asyncio
import json
import re
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from code_review_assistant.sub_agents.review_pipeline import extractor_agent
from code_review_assistant.services import get_session_service
from google.adk.runners import Runner
from google.genai.types import Content, Part


SQL_SCRIPT = """
BEGIN
  DECLARE max_fecha_origen DATE;
  DECLARE max_fecha_destino DATE;
  DECLARE fecha_corte TIMESTAMP;

  BEGIN TRANSACTION;

    SET max_fecha_origen = (SELECT MAX(DATE(dt_insertado)) FROM `habc-proj-dlh-qa.habc_capa_plata.ent_nombre_censo`);
    SET max_fecha_destino = (SELECT MAX(DATE(fecha_insercion)) FROM `habc-proj-dlh-qa.habc_capa_oro.dim_censo`);
    SET fecha_corte = CURRENT_TIMESTAMP();

    IF max_fecha_origen > max_fecha_destino THEN

        UPDATE `habc-proj-dlh-qa.habc_capa_oro.dim_censo`
        SET fecha_fin_vigencia = fecha_corte,
            activado = FALSE
        WHERE fecha_fin_vigencia = TIMESTAMP('9999-12-31');

        INSERT INTO `habc-proj-dlh-qa.habc_capa_oro.dim_censo` (
            censo_id, centro_sanitario_id_sap, unidad_enfermeria_id_sap,
            categoria_tratamiento_id_sap, grupo_censo_id_sap, grupo_censo_des,
            nombre_censo, censable, fecha_inicio_vigencia, fecha_fin_vigencia,
            fecha_insercion, activado
        ) (
            SELECT
                ROW_NUMBER() OVER() + (SELECT IFNULL(MAX(censo_id), 0) FROM `habc-proj-dlh-qa.habc_capa_oro.dim_censo`) AS censo_id,
                enc.id_centro_sanitario,
                enc.id_unidad_enfermeria,
                enc.id_categoria_tratamiento,
                enc.id_grupo_censo,
                enc.dsc_grupo_censo,
                enc.dsc_nombre_censo,
                mgcc.me_censable,
                TIMESTAMP(DATE('1990-01-01')) AS fecha_inicio_vigencia,
                TIMESTAMP('9999-12-31') AS fecha_fin_vigencia,
                TIMESTAMP(DATE(enc.dt_insertado)) AS fecha_insercion,
                TRUE AS activado
            FROM `habc-proj-dlh-qa.habc_capa_plata.ent_nombre_censo` AS enc
            LEFT JOIN `habc-proj-dlh-qa.habc_tablas_mapeo.map_grupo_censo_censable` AS mgcc
                ON enc.id_centro_sanitario = mgcc.centro_sanitario_id
               AND enc.dsc_nombre_censo = mgcc.nombre_censo
        );
    END IF;

  COMMIT TRANSACTION;

EXCEPTION WHEN ERROR THEN
  ROLLBACK TRANSACTION;
  RAISE USING MESSAGE = FORMAT("El Merge falló lógicamente. Error: %s", @@error.message);
END;
"""


def _parse_json_from_llm(raw: str | dict) -> dict:
    """Limpia markdown fences y parsea el JSON."""
    if isinstance(raw, dict):
        return raw
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("```").strip()
    return json.loads(cleaned)


def _print_state(state: dict) -> None:
    """Imprime el estado de forma legible."""
    KEYS_OF_INTEREST = [
        "extracted_metadata",
        "script_name",
        "source_tables",
        "destination_tables",
        "medallion_layer",
        "medallion_classification",
        "keys_used",
        "udfs",
        "schemas",
    ]

    print("\n" + "=" * 60)
    print("ESTADO DE LA SESIÓN")
    print("=" * 60)

    for key in KEYS_OF_INTEREST:
        value = state.get(key, "⚠️  NO ENCONTRADO")
        tipo = type(value).__name__

        if key == "extracted_metadata":
            # Muestra solo un preview del JSON crudo
            preview = str(value)[:120] + "..." if len(str(value)) > 120 else str(value)
            print(f"\n  [{tipo}] {key}:")
            print(f"    {preview}")
        elif isinstance(value, list):
            print(f"\n  [{tipo}] {key}: ({len(value)} elementos)")
            for item in value:
                print(f"    - {item}")
        elif isinstance(value, dict):
            print(f"\n  [{tipo}] {key}: ({len(value)} claves)")
            for k, v in value.items():
                # Para schemas muestra solo el conteo de columnas
                if key == "schemas":
                    print(f"    {k}: {len(v)} columnas")
                else:
                    print(f"    {k}: {v}")
        else:
            print(f"\n  [{tipo}] {key}: {value}")

    print("=" * 60)


def _verify_state(state: dict) -> None:
    """Verifica que las claves críticas se guardaron correctamente."""
    print("\n" + "=" * 60)
    print("VERIFICACIÓN")
    print("=" * 60)

    checks = {
        "source_tables poblado":      bool(state.get("source_tables")),
        "destination_tables poblado": bool(state.get("destination_tables")),
        "medallion_layer presente":   bool(state.get("medallion_layer")),
        "keys_used poblado":          bool(state.get("keys_used")),
        "schemas poblado":            bool(state.get("schemas")),
        "extracted_metadata crudo":   bool(state.get("extracted_metadata")),
    }

    all_passed = True
    for descripcion, resultado in checks.items():
        icono = "✅" if resultado else "❌"
        print(f"  {icono}  {descripcion}")
        if not resultado:
            all_passed = False

    print()
    if all_passed:
        print("  🎉 Todas las claves se guardaron correctamente.")
    else:
        print("  ⚠️  Algunas claves no se encontraron — revisa el callback.")
    print("=" * 60)


async def test():
    session_service = get_session_service()

    runner = Runner(
        agent=extractor_agent,
        app_name="test_extractor",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="test_extractor",
        user_id="test_user",
    )

    print(f"Sesión creada: {session.id}")
    print("Ejecutando extractor_agent...\n")

    message = Content(
        role="user",
        parts=[Part(text=f"Analiza este script SQL:\n\n{SQL_SCRIPT}")]
    )

    # Consume todos los eventos; nos interesa el final
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=message,
    ):
        if event.is_final_response():
            print("=== Respuesta final del agente ===")
            print(event.content.parts[0].text)

    # Lee el estado final de la sesión
    session_final = await session_service.get_session(
        app_name="test_extractor",
        user_id="test_user",
        session_id=session.id,
    )

    state = session_final.state

    # Si el callback aún no desempaca, intenta parsear extracted_metadata manualmente
    if not state.get("source_tables") and state.get("extracted_metadata"):
        print("\n⚠️  Las claves individuales no están en el estado.")
        print("   Puede que el callback no esté registrado. Parseando extracted_metadata manualmente...\n")
        try:
            metadata = _parse_json_from_llm(state["extracted_metadata"])
            # Muestra lo que habría guardado el callback
            print(f"  source_tables:      {metadata.get('source_tables')}")
            print(f"  destination_tables: {metadata.get('destination_tables')}")
            print(f"  medallion_layer:    {metadata.get('medallion_layer')}")
            print(f"  keys_used:          {metadata.get('keys_used')}")
            print(f"  schemas (tablas):   {list(metadata.get('schemas', {}).keys())}")
        except Exception as e:
            print(f"  Error al parsear: {e}")

    _print_state(state)
    _verify_state(state)


if __name__ == "__main__":
    asyncio.run(test())