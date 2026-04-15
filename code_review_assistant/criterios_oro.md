### 1. Transacciones — BEGIN / COMMIT / ROLLBACK

- Estructura: BEGIN > BEGIN TRANSACTION > DML > COMMIT > EXCEPTION > ROLLBACK > END [✓ OBLIGATORIO]
- EXCEPTION WHEN ERROR THEN seguido de ROLLBACK TRANSACTION [✓ OBLIGATORIO]
- Todo DML dentro del bloque transaccional [✓ OBLIGATORIO]
- DECLARE de variables ANTES de BEGIN TRANSACTION [✓ OBLIGATORIO]

### 2. Estrategia de Carga e Idempotencia

- Idempotencia: El script debe poder ejecutarse N veces sin duplicar datos ni corromper el estado. [✓ OBLIGATORIO]
  -Data Pruning: El script DEBE limitar el escaneo de datos en la tabla destino. Debe contener un filtro en la cláusula ON del MERGE o en un WHERE que utilice la columna de particionamiento (ej. fecha_carga, id_lote, o periodo). El filtro de pruning debe ser consistente con los datos de la fuente para asegurar que solo se reemplacen los registros del lote actual[✓ OBLIGATORIO]

### 3. Calidad y Validaciones de Datos

- SELECT \* prohibido en INSERT destino — columnas explícitas siempre [✓ OBLIGATORIO]
- Columnas del INSERT listadas y alineadas con el SELECT [✓ OBLIGATORIO]
- Columna activado (BOOLEAN) con valores TRUE/FALSE correctos según SCD2 [✓ OBLIGATORIO]
  -Validar tipo de datos de la fuente contra destino
- Tipos de datos de auditoría:`fecha_creacion`: DATETIME _ `fecha_actualizacion`: TIMESTAMP _ `activado`: BOOLEAN (Valores coherentes con SCD2) [✓ OBLIGATORIO]

### 4. Patrones BigQuery del Equipo

- Lee de tablas Plata (habc_capa_plata._) y/o tablas Oro (habc_capa_oro._) — nunca de Bronce [✓ OBLIGATORIO]
- Consistencia de entorno: Validación estricta de que los Project IDs coinciden con el ambiente (QA/PRD).[✓ OBLIGATORIO]

### 5. Nomenclatura y Seguridad

- Nombre de archivo: dim\_[nombre]\_oro.sql | h[nombre]\_oro.sql | hpx[nombre]\_oro.sql [✓ OBLIGATORIO]
- Un script = una tabla destino (Single Responsibility) [✓ OBLIGATORIO]
