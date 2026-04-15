BEGIN
    -- Declaración de variables
    DECLARE max_fecha_origen DATE;
    DECLARE max_fecha_destino DATE;
    DECLARE fecha_corte TIMESTAMP;

    BEGIN TRANSACTION;

        -- Asignamos los valores a las variables
        SET max_fecha_origen = (SELECT MAX(DATE(dt_insertado)) FROM `habc-proj-dlh-qa.habc_capa_plata.ent_nombre_censo`);
        SET max_fecha_destino = (SELECT MAX(DATE(fecha_insercion)) FROM `habc-proj-dlh-qa.habc_capa_oro.dim_censo`);
        SET fecha_corte = CURRENT_TIMESTAMP();

        -- Se ejecuta solo si la tabla de origen (ent_nombre_censo) tiene datos nuevos.
        IF max_fecha_origen > max_fecha_destino THEN

            -- 1. DESACTIVAR TODOS LOS REGISTROS ACTIVOS en la tabla destino.
            UPDATE `habc-proj-dlh-qa.habc_capa_oro.dim_censo`
            SET fecha_fin_vigencia = fecha_corte,
                activado = FALSE
            WHERE fecha_fin_vigencia = TIMESTAMP('9999-12-31');

            -- 2. INSERTAR LA TOTALIDAD DE LA TABLA DE ORIGEN como los nuevos registros activos.
            INSERT INTO `habc-proj-dlh-qa.habc_capa_oro.dim_censo` (
                censo_id,
                centro_sanitario_id_sap,
                unidad_enfermeria_id_sap,
                categoria_tratamiento_id_sap,
                grupo_censo_id_sap,
                grupo_censo_des,
                nombre_censo,
                censable,
                fecha_inicio_vigencia,
                fecha_fin_vigencia,
                fecha_insercion,
                activado
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
                    TIMESTAMP(DATE(enc.dt_insertado))  AS fecha_insercion,
                    TRUE AS activado
                FROM `habc-proj-dlh-qa.habc_capa_plata.ent_nombre_censo` AS enc
                LEFT JOIN `habc-proj-dlh-qa.habc_tablas_mapeo.map_grupo_censo_censable` AS mgcc 
                    ON enc.id_centro_sanitario = mgcc.centro_sanitario_id AND enc.dsc_nombre_censo = mgcc.nombre_censo  -- Sin WHERE, inserta todos los datos de origen.
            );
        END IF;

    COMMIT TRANSACTION;
EXCEPTION WHEN ERROR THEN
    ROLLBACK TRANSACTION;
    RAISE USING MESSAGE = FORMAT("El Merge falló lógicamente. Error: %s", @@error.message);
END;