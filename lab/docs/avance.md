# Estado del laboratorio

Las evidencias locales y el smoke acelerado no acreditan una hora real. Ya existe un despliegue en GCP y evidencia exportada del smoke.

| Fase | Estado | Evidencia o dependencia |
| --- | --- | --- |
| 1 Preparación | validado | PDF preservado; Python 3.13 y dependencias instalados; eliminaciones previas intactas |
| 2 Backend | validado | Alcance local: contrato, logs, latencia y fallas; Firestore emulado entre clientes/procesos y transacción concurrente |
| 3 Simulador | validado | Alcance local: plan de 6000; smoke HTTP de 60; CSV correlacionado; concurrencia, transporte e interrupción probados |
| 4 Infraestructura | validado | Proyecto adfasdfasfd-1899a confirmado; login/ADC; plan real y apply completados tras un reintento del build |
| 5 Observabilidad | validado | Capturas del usuario confirman las cuatro fuentes, incluidos errores SQL y latencia SQL p50/p95 tras el segundo ajuste |
| 6 Smoke GCP | validado | Contrato HTTP aprobado, 500 artificial correlacionado, 60/60 intentos y logs, SQL de latencia ejecutado con valores y gráfico visible |
| 7 Hora oficial | validado | official-20261031T025905Z: 6000 programados/enviados/completados, 3600.006 s, escala 1, 6000 respuestas y cero errores de transporte |
| 8 Análisis | validado | Reporte en README raíz, 4 capturas, 3 figuras y datos reales de Monitoring. Contadores CSV/logs/nativo/usuario coinciden en 6000; diferencia de 6 muestras de latencia nativa documentada |
| 9 Cierre | pendiente | Recursos GCP activos; destruir solamente después de preservar evidencia oficial |

## Criterios de aceptación

- [x] Estructura de entrega y README reproducible; PDF original intacto.
- [x] Backend handle con tres operaciones, códigos, fallas y latencia.
- [x] Persistencia compartida y transición atómica verificadas en emulador oficial, incluso desde otro proceso.
- [x] Logs JSON centralizados con negocio, IDs, severidad y resultados consistentes.
- [x] Plan exacto/reproducible, escenario por configuración y despacho concurrente.
- [x] CSV por intento, incluidos errores de transporte; evidencia parcial e incompleta conservada en interrupción.
- [x] Pruebas locales y validación Terraform; resultados en `evidence/local-validation/checks.json`.
- [x] Función desplegada y outputs obtenidos; URL invocada y vista Analytics consultada con éxito.
- [x] Métricas existentes antes del primer tráfico GCP: createTime 2026-10-31T02:02:58/59Z, archivos en evidence/gcp-setup/.
- [x] Una ventana real de 3600 s y 6000 intentos: summary.json completo y CSV con 6000 IDs únicos, todos dentro de la ventana.
- [x] Dashboard único con las cuatro fuentes: filtros SQL oficiales aplicados, JSON final exportado y capturas guardadas.
- [x] Evidencia oficial: configuración, CSV, resumen, 6000 logs, métricas reales, SQL, capturas y análisis en README.
- [ ] Limpieza de GCP verificada: infraestructura activa y cierre pendiente.

## Despliegue y corrección de SQL en curso

- Función: https://orders-api-gfr6cqd5yq-uc.a.run.app
- Dashboard: https://console.cloud.google.com/monitoring/dashboards/builder/9e847e3b-cd26-45f6-9cdf-de9c34ffbf93?project=adfasdfasfd-1899a
- Contrato: check-20261031T020537Z, 54 intentos, HTTP aprobado y 500 artificial confirmado.
- Smoke: smoke-20261031T020723Z, 60 intentos en 7.2 s, 60 logs emparejados sin duplicados ni diferencias de código.
- SQL verificado en consola: books 7/20=0.35, clothing 5/18=0.2777778, electronics 11/22=0.5.
- `evidence/smoke-20261031T020723Z/dashboard.json` es la exportación real de nueve widgets, incluida la gráfica añadida por el usuario.
- El usuario aplicó los dos ajustes y confirmó por captura que los SQL originales de errores y de latencia muestran datos. La latencia usa una sola medida `latency_ms` y una etiqueta `series` que combina segmento, operación y p50/p95. La consulta fue ejecutada en Analytics y el usuario confirmó filas con valores.
- `observability/dashboard.smoke-review.json` corresponde a la configuración aplicada, con los nueve widgets preservados; todavía hace falta una nueva exportación real tras este último cambio. Cinco pruebas locales de observabilidad pasan.
- `infra/terraform.tfvars` selecciona esa propuesta mediante dashboard_override_file. Para cambiar posteriormente de corrida, renderizar desde el JSON final exportado y actualizar ese override; las variables analytics_* no afectan un archivo override ya renderizado.

La implementación y el smoke no equivalen al laboratorio completo. Se continúa paso a paso con el usuario; [pasos_gcp.md](pasos_gcp.md) documenta el procedimiento general.

## Hora oficial completada

Corrida `official-20261031T025905Z`, preparación de 1119 recursos, quietud 120 s y escala 1. Inicio: 30 de octubre 21:01:22 y fin 22:01:22 (Guatemala, UTC−6). Se verificaron resumen completo, 3600.006 s y 6000 filas/IDs únicos. Los 6000 logs se emparejan sin duplicados ni discrepancias de código: 5360 respuestas 2xx, 526 respuestas 4xx y 114 respuestas 5xx; todos los 5xx son simulated_failure, sin internal_error ni errores de transporte.

La tasa 4xx de electronics fue 126/1555=8.10 % fuera del escenario y 71/459=15.47 % dentro de [35,45). El usuario aplicó el dashboard con todos los SQL oficiales. El JSON final se exportó nuevamente y se guardaron las cuatro capturas. Los datos completos están en analysis.json y el análisis principal en el README raíz.

Por corrección explícita del usuario, el formato final es el README raíz, con encabezado «Mathew Alexander Cordero Aquino - 22982» y enlace a la rama labmonitoring. No se genera PDF del reporte. El cierre de GCP sigue pendiente.

## Conciliación de fuentes y calidad de evidencia

Monitoring confirma 6000 solicitudes nativas y 6000 finalizaciones de la métrica de logs, separadas de 1154 intentos preparatorios. Ambas fuentes coinciden en clases HTTP con el CSV. La distribución nativa de latencia reporta 6006 muestras; se conserva la diferencia de 6 y no se interpreta como intentos adicionales. La distribución de logs tiene 6000 muestras. El README explica los bins de un minuto, el pico preparatorio de las capturas y la causa no aislada de esa diferencia de distribución. Los archivos están en monitoring/reconciliation.json y report-data.json de la corrida.
