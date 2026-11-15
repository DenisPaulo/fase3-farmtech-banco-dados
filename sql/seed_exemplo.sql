-- Cadastro inicial alinhado a seed_cadastros_iniciais em src/crud_sensores.py.
-- Rode depois de sql/schema_oracle.sql. A segunda execução encontra CULTURAS preenchida e encerra.

DECLARE
    v_n NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_n FROM CULTURAS;
    IF v_n = 0 THEN
        INSERT INTO CULTURAS (
            nome_cultura, variedade, umidade_ideal_min, umidade_ideal_max,
            ph_ideal_min, ph_ideal_max, n_min_mg_dm3, p_min_mg_dm3, k_min_mg_dm3
        ) VALUES ('Café Arábica', 'Catuaí Vermelho IAC 144', 45, 65, 5.5, 6.5, 30, 12, 90);

        INSERT INTO CULTURAS (
            nome_cultura, variedade, umidade_ideal_min, umidade_ideal_max,
            ph_ideal_min, ph_ideal_max, n_min_mg_dm3, p_min_mg_dm3, k_min_mg_dm3
        ) VALUES ('Milho Safrinha', 'Híbrido Simples', 50, 70, 5.8, 6.8, 35, 15, 100);

        INSERT INTO TALHOES (id_cultura, codigo_talhao, nome_talhao, area_ha, altitude_m)
        VALUES (1, 'TL-01', 'Talhão Norte — Café Catuaí', 42.5, 980);

        INSERT INTO TALHOES (id_cultura, codigo_talhao, nome_talhao, area_ha, altitude_m)
        VALUES (1, 'TL-02', 'Talhão Sul — Café Bourbon', 38, 1025);

        INSERT INTO TALHOES (id_cultura, codigo_talhao, nome_talhao, area_ha, altitude_m)
        VALUES (1, 'TL-03', 'Talhão Leste — Café Mundo Novo', 51, 945);

        INSERT INTO TALHOES (id_cultura, codigo_talhao, nome_talhao, area_ha, altitude_m)
        VALUES (2, 'TL-04', 'Talhão Oeste — Pivô Central', 64, 890);

        INSERT INTO SENSORES (id_talhao, codigo_sensor, tipo_sensor, modelo_hw, status_operacional)
        VALUES (1, 'ESP32-TL01', 'Multissensor Solo/Clima', 'ESP32 + DHT22 + LDR + NPK', 'ATIVO');

        INSERT INTO SENSORES (id_talhao, codigo_sensor, tipo_sensor, modelo_hw, status_operacional)
        VALUES (2, 'ESP32-TL02', 'Multissensor Solo/Clima', 'ESP32 + DHT22 + LDR + NPK', 'ATIVO');

        INSERT INTO SENSORES (id_talhao, codigo_sensor, tipo_sensor, modelo_hw, status_operacional)
        VALUES (3, 'ESP32-TL03', 'Multissensor Solo/Clima', 'ESP32 + DHT22 + LDR + NPK', 'ATIVO');

        INSERT INTO SENSORES (id_talhao, codigo_sensor, tipo_sensor, modelo_hw, status_operacional)
        VALUES (4, 'ESP32-TL04', 'Multissensor Solo/Clima', 'ESP32 + DHT22 + LDR + NPK', 'ATIVO');
    END IF;
    COMMIT;
END;
/

PROMPT Seed de culturas, talhoes e sensores concluido.
