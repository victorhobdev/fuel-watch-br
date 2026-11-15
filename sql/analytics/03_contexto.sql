-- O contexto é opcional e nunca deve multiplicar ou substituir a coleta oficial.
CREATE OR ALTER VIEW analise_hist.coletas_contexto AS
SELECT b.*, d.inicio_semana_iso,
       p.ano_referencia AS populacao_ano, p.data_referencia AS populacao_data_referencia,
       p.populacao, p.source_sha256 AS populacao_source_sha256,
       CASE WHEN p.populacao IS NULL THEN 'sem_referencia' ELSE 'disponivel' END AS populacao_status,
       w.station_id, w.nearest_station_id, w.distance_km, w.association_status,
       w.expected_hours, w.reported_hours, w.valid_temperature_hours, w.valid_rain_hours,
       w.temperature_fraction, w.rain_fraction, w.temperature_eligible, w.rain_eligible,
       w.mean_temperature_degC, w.observed_rain_mm, w.partial_boundary_week,
       COALESCE(w.coverage_status, 'sem_registro_contexto') AS weather_status
FROM gold_hist.business_published b
JOIN gold_hist.dim_data d ON b.data_coleta = d.data
LEFT JOIN lh_fuelwatch.dbo.f2_context_population p
 ON b.municipio_ibge = p.municipio_ibge AND YEAR(b.data_coleta) = p.ano_referencia
LEFT JOIN lh_fuelwatch.dbo.f2_context_weather_municipal_weekly w
 ON b.municipio_ibge = w.municipio_ibge AND d.inicio_semana_iso = w.week_start;
