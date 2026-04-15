### 1. Transacciones — BEGIN / COMMIT / ROLLBACK

- Estructura: BEGIN > BEGIN TRANSACTION > DML > COMMIT > EXCEPTION > ROLLBACK > END [✓ OBLIGATORIO]
- EXCEPTION WHEN ERROR THEN seguido de ROLLBACK TRANSACTION [✓ OBLIGATORIO]
- Todo DML dentro del bloque transaccional [✓ OBLIGATORIO]

### 2. Estrategia de Carga e Idempotencia

- Tablas transaccionales: MERGE ON llave_única con MATCHED / NOT MATCHED y opflag D/U/I [✓ OBLIGATORIO] + Data Pruning: El script DEBE limitar el escaneo de datos en la tabla destino. Debe contener un filtro en la cláusula ON del MERGE o en un WHERE que utilice la columna de particionamiento (ej. fecha_carga, id_lote, o periodo). El filtro de pruning debe ser consistente con los datos de la fuente para asegurar que solo se reemplacen los registros del lote actual [✓ OBLIGATORIO]
- MERGE: DELETE para opflag=D, UPDATE para opflag U/I, INSERT para NOT MATCHED [✓ OBLIGATORIO]
- Tablas históricas: UPDATE activado=FALSE + INSERT activado=TRUE en la misma transacción [✓ OBLIGATORIO]
- Idempotencia: El script debe poder ejecutarse N veces sin duplicar datos ni corromper el estado. [✓ OBLIGATORIO]

### 3. Calidad y Validaciones de Datos

- SELECT \* prohibido en INSERT destino — columnas explícitas siempre [✓ OBLIGATORIO]
- Columnas del INSERT listadas y alineadas con el SELECT [✓ OBLIGATORIO]
- Columnas insertado (TIMESTAMP) y system (STRING) presentes [✓ OBLIGATORIO]
- Columna activado (BOOLEAN) presente [✓ OBLIGATORIO]
- Columna de timestamp de carga presente [✓ OBLIGATORIO]
- Filtro de lote de carga presente, ej: WHERE id_historico = 1 (Sólo aplica para tablas transaccionales) [✓ OBLIGATORIO]
- Validar si los tipos de datos de la tabla fuente y destino son iguales
- Validar que la vista fuente devuelve filas antes del DML [○ RECOMENDADO]
- Validar tipos de datos específicos [✓ OBLIGATORIO]: _ fecha_creacion (DATETIME) _ fecha_actualizacion (TIMESTAMP) \* activado (BOOLEAN)

### 4. Patrones BigQuery del Equipo

- Lee desde vistas vw*limp*[tabla] de habc-proj-etl-[qa|prd].habc_vistas_bronce — nunca tablas raw [✓ OBLIGATORIO]
- Filtro de partición o lote en queries sobre tablas grandes [✓ OBLIGATORIO]
  -- Proyecto ETL correcto: habc-proj-etl-[qa|prd] — no usar proyecto dlh en Bronce [✓ OBLIGATORIO]
- Consistencia de entorno: Validación estricta de que los Project IDs coinciden con el ambiente (QA/PRD). [✓ OBLIGATORIO]

### 5. Nomenclatura y Seguridad

- Nombre de archivo: [tabla]\_trans_bronce.sql o [tabla]\_trans_historia.sql [✓ OBLIGATORIO]
- Un script = una tabla destino (Single Responsibility) [✓ OBLIGATORIO]
