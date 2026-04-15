## CRITERIOS DE EVALUACIÓN - PLATA

### 2. Transacciones — BEGIN / COMMIT / ROLLBACK

- Estructura: BEGIN > BEGIN TRANSACTION > DML > COMMIT > EXCEPTION > ROLLBACK > END [✓ OBLIGATORIO]
- EXCEPTION WHEN ERROR THEN seguido de ROLLBACK TRANSACTION [✓ OBLIGATORIO]
- Todo DML dentro del bloque transaccional [✓ OBLIGATORIO]
- DECLARE de variables antes de BEGIN TRANSACTION [○ RECOMENDADO]

### 3. Estrategia de Carga e Idempotencia

- Idempotencia: El script debe poder ejecutarse N veces sin duplicar datos ni corromper el estado. [✓ OBLIGATORIO]
  -Data Pruning: El script DEBE limitar el escaneo de datos en la tabla destino. Debe contener un filtro en la cláusula ON del MERGE o en un WHERE que utilice la columna de particionamiento (ej. fecha_carga, id_lote, o periodo). El filtro de pruning debe ser consistente con los datos de la fuente para asegurar que solo se reemplacen los registros del lote actual

### 4. Calidad y Validaciones de Datos

- SELECT \* prohibido en INSERT destino — columnas explícitas siempre [✓ OBLIGATORIO]
- Columnas del INSERT listadas y alineadas con el SELECT [✓ OBLIGATORIO]
- Columna dt_insertado (o equivalente) presente — requerida por Oro [✓ OBLIGATORIO]
- VALIDACIÓN DE TIPOS (SCRIPT VS METADATOS) [✓ OBLIGATORIO]: dt_insertado -> debe ser TIMESTAMP, id_sistema -> integer

### 5. Patrones BigQuery del Equipo

- Lee SOLO de tablas Bronce (habc-proj-etl-[qa|prd].habc_capa_bronce.[tabla]) o capa plata (sólo tabla habc-proj-dlh-[qa/prd].en sistemas para el campo de id_sistema) [✓ OBLIGATORIO]
- Consistencia de entorno: prd lee solo tablas prd; qa lee solo tablas qa [✓ OBLIGATORIO]
- Filtro de partición en queries sobre tablas grandes [○ RECOMENDADO]

### 6. Nomenclatura y Seguridad

- Nombre de archivo: tx*[nombre]\_plata.sql o ent*[nombre]\_plata.sql [✓ OBLIGATORIO]
- Un script = una tabla destino (Single Responsibility) [✓ OBLIGATORIO]
