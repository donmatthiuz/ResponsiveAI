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
| 7 Hora oficial | en curso | official-20261031T025905Z:1119 recursos preparados; escala1; t0=2026-10-31T03:01:22.409460Z, fin previsto04:01:22.409460Z; aún sin resumen final |
| 8 Análisis | en curso | Informe de smoke GCP generado y correlación 60/60 sin discrepancias; faltan datos de la hora oficial |
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
- [ ] Una ventana real de 3600 s con 6000 intentos: en curso; esperar summary.json para verificar completitud y conteos.
- [x] Dashboard único con las cuatro fuentes visibles en el smoke: incluye ambos SQL originales y logs; falta retarget y evidencia de la hora oficial.
- [ ] Evidencia oficial de una hora: ya hay JSON y 60 logs del smoke GCP; falta la corrida oficial, captura final y su análisis.
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

## Hora oficial en curso

Corrida `official-20261031T025905Z`, preparación completa de1119 recursos, quietud120 s y escala1. Inicio medido:30 de octubre21:01:22 (Guatemala, UTC−6); fin previsto de envíos:22:01:22. Se verificó el calendario y se observaron las primeras filas CSV. No se acredita la hora completa ni los6000 intentos hasta revisar el resumen final. El manifiesto de fuentes previo se copió al directorio de evidencia de esa corrida.
