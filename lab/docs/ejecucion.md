# Registro de ejecución

Fecha de trabajo local: **30 de octubre de 2026**, America/Guatemala. Los artefactos técnicos guardan UTC, por lo que sus fechas empiezan el 31 de octubre. Commit de referencia inicial: `3a9bfda`; la implementación nueva está sin commit. El manifiesto `evidence/local-validation/source_hashes.json` identifica sus fuentes finales.

## Herramientas verificadas

| Herramienta | Versión |
| --- | --- |
| Python de pruebas | 3.13.15 |
| Functions Framework | 3.10.2 |
| Firestore Python | 2.34.1 |
| HTTPX | 0.28.1 |
| NumPy | 2.5.4 |
| pytest / pytest-asyncio | 9.2.0 / 1.4.1 |
| Ruff | 0.17.3 |
| Monitoring dashboards SDK | 2.22.0 |
| Terraform | 1.13.5 |
| Proveedor Google / archive | 6.50.0 / 2.8.1 |
| Firestore emulator | 1.19.8, JRE 21 de Eclipse Adoptium |

Las versiones transitivas están en `requirements-lock.txt`. Python, Terraform, Java y el JAR del emulador se descargaron en `/tmp` sin modificar instalaciones del sistema. El SDK gcloud existe en `$HOME/google-cloud-sdk/bin`, fuera del PATH inicial. Inicialmente no había ADC para el laboratorio; posteriormente el usuario confirmó el proyecto `adfasdfasfd-1899a`, facturación y autenticación CLI/ADC antes del despliegue.

## Pruebas y verificaciones locales

- Suite funcional, simulador, logging, integración y observabilidad: resultado final en `evidence/local-validation/checks.json`.
- Integración real contra el emulador en `127.0.0.1:8085`: dos clientes y un proceso separado leen el mismo pedido; la cancelación concurrente confirma una sola transición.
- Se cubren tasa de fallas 0 y 1, umbral aleatorio controlado, fallas antes de escribir, validación de configuración, latencia artificial incluida, cardinalidad acotada y propagación de IDs.
- Simulador: plan reproducible y truncado, límites del escenario, superposiciones rechazadas, peticiones solapadas con servidor lento, tres reintentos de preparación, fallo 403 sin reintento, CSV de errores de transporte, Ctrl+C/cancelación y ventana vencida.
- Terraform: init completado y lockfile generado; fmt/validate aprobados; cuatro pruebas mock aprobadas. El plan usa Google simulado y **no acredita un plan contra GCP**, credenciales, permisos, cuotas ni facturación.
- Dashboard: JSON completo validado contra discovery REST oficial, y sus widgets estables contra el SDK. No se ejecutó SQL en Analytics ni se verificó ingestión.

## Dry-run de referencia

Comando desde la raíz del repositorio:

```bash
lab/.venv/bin/python lab/simulator/simulator.py --config lab/simulator/config.json \
  --output lab/evidence/local-dry-run/requests.csv --run-id local-dry-run --dry-run
```

6000 eventos, cero envíos. Offsets mínimo 8.506 s y máximo 3597.743 s; media 29.906 min. Plan: 5474 válidos, 161 invalid_payload, 181 not_found y 184 invalid_state. No son resultados HTTP ni predicción exacta de una corrida real.

## Smoke local acelerado

Backend: Firestore emulado, `FAILURE_RATE=0.02`, `EXTRA_LATENCY_MS=15`, Functions Framework en `127.0.0.1:8080`. `DEBUG=false` explícito porque el entorno anfitrión tenía un valor no booleano que impedía iniciar la CLI.

```bash
cd lab
.venv/bin/python simulator/simulator.py --config simulator/config.smoke.json \
  --output evidence/local-smoke/requests.csv --run-id local-smoke --time-scale 0.002
```

- t0: `2026-10-31T01:05:09.492136+00:00`.
- Fin de ventana: `2026-10-31T01:05:16.692136+00:00`.
- Fin real: `2026-10-31T01:05:16.693745+00:00`.
- Ventana comprimida 7.2 s; 60 programados/enviados/completados; 60 respuestas, sin error de transporte.
- HTTP: 201=23, 200=14, 400=8, 404=8, 409=7. No se observó 500 en esta muestra; una prueba contractual separada sí lo observó.
- Logs medidos=60; IDs correlacionados=60; duplicados=0; diferencias de código=0. Preparación en archivo aparte y excluida del análisis.
- Latencia cliente p50=21.750 ms, p95=31.282 ms; retraso de despacho p50=0.842 ms, p95=1.831 ms.

`evidence/local-smoke/rendered/dashboard.json` es una **plantilla renderizada para validar estructura**, con proyecto ficticio demo; no es exportación de GCP. No existe `dashboard.png` real y no se fabricó una captura.

## Comprobación HTTP contractual

`evidence/local-contract/http_cases.json` y `logs_sample.jsonl` conservan 11 intentos. La herramienta registró el 500 y luego reintentó una comprobación válida, fuera del tráfico medido.

| Código | Request ID de ejemplo |
| --- | --- |
| 201 | `local-contract-check-0001` |
| 200 | `local-contract-check-0002` |
| 409 | `local-contract-check-0004` |
| 400 | `local-contract-check-0005` |
| 404 | `local-contract-check-0007` |
| 405 | `local-contract-check-0009` |
| 500 simulated_failure | `local-contract-check-0010` |

## Ejecución GCP realizada y pendientes

| Campo | Estado |
| --- | --- |
| Proyecto / facturación | adfasdfasfd-1899a, confirmados por el usuario |
| ADC | Usuario completó login y asignó quota project |
| Plan real y apply | Completados; función orders-api activa tras un reintento del primer build |
| URL | https://orders-api-gfr6cqd5yq-uc.a.run.app |
| Creación real de métricas | 2026-10-31T02:02:58.257782122Z contador; 02:02:59.225136861Z distribución; evidencia gcp-setup/ |
| Contrato HTTP | check-20261031T020537Z, 54 intentos, aprobado; simulated_failure en request check-0053 y log correlacionado |
| Smoke remoto | smoke-20261031T020723Z, escala 0.002, 60/60 respuestas, sin transporte; inicio 02:07:27.947662Z y fin 02:07:35.148179Z |
| Correlación remota | 60 logs y 60 filas CSV; cero duplicados y discrepancias de código |
| Señales reales | Gráficas nativas y métricas de logs y panel de logs comprobados por el usuario; Analytics devuelve 60 eventos |
| Dashboard | projects/248394644314/dashboards/9e847e3b-cd26-45f6-9cdf-de9c34ffbf93, nueve widgets tras añadir la gráfica manual de errores |
| SQL errores | Tres filas, books 20/0.35, clothing 18/0.2777778, electronics 22/0.5; gráfica manual visible en el dashboard |
| Reparación de SQL | Aplicada y comprobada: errores y latencia p50/p95 visibles; JSON final exportado con las tres consultas SQL filtradas a la corrida oficial |
| Hora oficial de 6000 intentos / 3600 s | Completada: official-20261031T025905Z; inicio 03:01:22.409460Z; fin 04:01:22.415622Z; duración 3600.006192 s; 6000 intentos y respuestas |
| Exportación/captura | 6000 logs, dashboard final, cuatro capturas y series/descriptores de Monitoring guardados |
| Análisis con métricas nativas y SQL ejecutado | README raíz completado; tres figuras reproducibles y conciliación de cuatro fuentes; seis muestras nativas adicionales documentadas |
| Terraform destroy | Pendiente al finalizar análisis oficial y guardar evidencia; recursos reales activos |
| Limpieza local | Se cierran los procesos de pruebas; evidencia y entorno virtual se conservan |

El primer build falló al leer el bucket de staging a pesar del rol objectViewer declarado. Se comprobó el binding, se dejó tiempo de propagación y el único reintento completó el build. La propagación de IAM es la explicación probable; no se agregaron roles adicionales para ese reintento.

La exportación del dashboard permitió comparar la gráfica SQL manual que el usuario confirmó con las originales. Se adoptaron sus parámetros de dimensión y desglose (límite positivo, selección count y orden descendente). Después se migró la latencia a una sola medida y un solo desglose que incorpora segmento/operación/percentil. El usuario ejecutó la consulta en Analytics, aplicó el cambio y confirmó por captura que ambos paneles muestran datos. Se conserva la gráfica manual como referencia. Cinco pruebas locales de observabilidad pasan, incluida la migración de exportaciones previas.

Configuración oficial: URL real, 6000 solicitudes, μ30, σ10, semilla42, invalid_share0.08, electronics [35,45). El usuario ejecutó el simulador con escala1 y systemd-inhibit. Se comprobaron 1119 recursos preparados, 120 s de quietud y una ventana de 3600 s. Inicio 2026-10-31T03:01:22.409460Z y fin 04:01:22.415622Z (30 de octubre 21:01:22 a22:01:22 en Guatemala). Se validaron summary.json completo, 6000 filas/IDs únicos sin transporte y 6000 logs con códigos coincidentes. Los 114 eventos 5xx son artificiales. Cliente: p50=110.312 ms, p95=248.941 ms, p99=554.284 ms; despacho p95=1.954 ms. Manifiesto de fuentes, capturas y reporte en README conservados. Falta el cierre.

La exportación adicional de Monitoring delimita bins de 03:01 a04:02 UTC. Los contadores nativo y de logs coinciden con las 6000 filas; el intervalo previo contiene 1154 intentos preparatorios, coherentes con preparation.jsonl. La distribución nativa tiene 6006 muestras frente a6000 de la distribución de logs: se mantiene esa discrepancia sin adjudicar una causa no demostrada. El reporte utiliza los logs individuales para los percentiles globales del backend.

El usuario cambió el formato solicitado de PDF a README. El reporte final está en `../../README.md`, con su nombre/carné, repositorio, análisis de las cinco preguntas, capturas y figuras. El laboratorio no se declara cerrado mientras falten destrucción y verificación de residuos.
