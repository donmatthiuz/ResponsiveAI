# Análisis de la corrida oficial

El [reporte principal está en el README de la raíz](../../README.md). Incluye las cinco preguntas del laboratorio, tablas, tres figuras reproducibles y las cuatro capturas originales del usuario.

## Datos verificados

- Corrida: `official-20261031T025905Z`, 6000 intentos y respuestas, 6000 IDs únicos y 6000 logs correlacionados sin duplicados ni diferencias de código.
- Ventana: 2026-10-31T03:01:22.409460Z a04:01:22.409460Z; proceso finalizado a04:01:22.415622Z. Duración3600.006192 s y escala1.
- Resultados:5360 éxitos,526 errores de cliente y114 fallas simuladas. No hubo internal_error ni errores de transporte.
- Contadores nativo de Cloud Run y basado en logs:6000 cada uno, con las mismas cantidades por clase HTTP que el CSV.

## Respuestas a las preguntas del dashboard

1. **Volumen.** Media del calendario29.906 min y desviación9.880 min; máximo274 solicitudes en[33,34). La forma concuerda con la normal truncada, sin exigir máximo exactamente en30.
2. **Códigos.** 2xx=89.33 %,4xx=8.77 %,5xx=1.90 %. Las114 fallas simuladas corresponden a2.08 % de las5474 solicitudes funcionalmente válidas. Intención y resultado se guardaron por separado.
3. **Escenario.** electronics:126/1555=8.10 % fuera de[35,45),71/459=15.47 % dentro, incremento1.91 veces. books:8.29→7.49 %; clothing:7.35→12.24 %. Solo electronics tenía el cambio programado; la variación de controles impide interpretar una sola corrida como prueba causal exclusiva.
4. **Latencia.** Cliente:p50=110.312 ms,p95=248.941 ms,p99=554.284 ms. Backend:p50=16.855 ms,p95=57.829 ms,p99=110.558 ms. Las tablas por operación/segmento están en el README y analysis.json. Hubo4 retrasos de despacho>100 ms,2 de ellos>1 s; máximo1576.438 ms, sin envíos fuera de la hora.
5. **Correlación.** request-005514, visible en la captura: consulta válida de books/premium, esperaba200 y recibió500 simulated_failure. Backend20.893 ms,cliente106.556 ms. Se cruzó con el CSV por su ID completo.

## Diferencias entre fuentes

La preparación confirmó1119 pedidos mediante1154 intentos HTTP:1125 éxitos y29 fallas artificiales. El intervalo previo de Monitoring contiene exactamente1154 solicitudes. El pico izquierdo de las capturas nativa y de logs incluye ese tráfico y no pertenece a los6000 intentos medidos. Las tablas y figuras reconstruidas lo excluyen.

Para incluir bins completos de60 s, la exportación cuantitativa de métricas utiliza03:01–04:02 UTC; SQL y los eventos mantienen los límites precisos y el run_id. Ambos contadores y la distribución de logs concilian en6000. La distribución nativa de latencia contiene6006 muestras (+0.10 %); no se aisló la causa y no se interpreta como intentos adicionales. Se conserva el dato original. Los percentiles globales del backend se calcularon desde los6000 logs, no promediando percentiles de instancias.

Las métricas de logs fueron creadas a02:02:58/59 UTC, antes del tráfico. SQL usa APPROX_QUANTILES; las métricas de distribución usan buckets; esos estimadores pueden diferir de los percentiles empíricos sobre muestras individuales.

## Evidencias y alcance

- [Análisis estructurado](../evidence/official-20261031T025905Z/analysis.json).
- [Conciliación de Monitoring](../evidence/official-20261031T025905Z/monitoring/reconciliation.json).
- [Ejemplo correlacionado y datos adicionales](../evidence/official-20261031T025905Z/report-data.json).
- [Dashboard final](../evidence/official-20261031T025905Z/dashboard.json), [capturas](../evidence/official-20261031T025905Z/captures) y [figuras](../evidence/official-20261031T025905Z/figures).

El informe y la evidencia de la ejecución están completos. La destrucción de recursos y la verificación de residuos siguen pendientes; no se declaran realizadas. Los resultados locales y del smoke permanecen en sus directorios originales y no se presentan como sustitutos de la hora real.
