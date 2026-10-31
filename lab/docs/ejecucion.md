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
| Reparación de SQL | Aplicada y comprobada por el usuario: errores y latencia p50/p95 visibles; nueva exportación final del dashboard pendiente |
| Hora oficial de 6000 intentos / 3600 s | No ejecutada |
| Exportación/captura | JSON real y 60 logs exportados; falta captura final y exportación tras validar todos los paneles |
| Análisis con métricas nativas y SQL ejecutado | Pendiente |
| Terraform destroy | Pendiente al finalizar análisis oficial y guardar evidencia; recursos reales activos |
| Limpieza local | Se cierran los procesos de pruebas; evidencia y entorno virtual se conservan |

El primer build falló al leer el bucket de staging a pesar del rol objectViewer declarado. Se comprobó el binding, se dejó tiempo de propagación y el único reintento completó el build. La propagación de IAM es la explicación probable; no se agregaron roles adicionales para ese reintento.

La exportación del dashboard permitió comparar la gráfica SQL manual que el usuario confirmó con las originales. Se adoptaron sus parámetros de dimensión y desglose (límite positivo, selección count y orden descendente). Después se migró la latencia a una sola medida y un solo desglose que incorpora segmento/operación/percentil. El usuario ejecutó la consulta en Analytics, aplicó el cambio y confirmó por captura que ambos paneles muestran datos. Se conserva la gráfica manual como referencia. Cinco pruebas locales de observabilidad pasan, incluida la migración de exportaciones previas.

Configuración previa a la hora oficial comprobada: URL real,6000 solicitudes, μ30,σ10,semilla42,invalid_share0.08, electronics [35,45). El simulador tendrá escala1, preparación fuera del reloj,120 s de quietud,3600 s de ventana y drenado final. `systemd-inhibit` está disponible para bloquear suspensión durante la ejecución. El manifiesto de fuentes y versiones previo se conserva en `evidence/pre-official/manifest.json`. La hora todavía no se marca como iniciada hasta que el usuario ejecute el comando y confirme la preparación.

No se puede declarar el laboratorio completo mientras la hora oficial, la observabilidad completa, el análisis y el cierre sigan pendientes. Los pasos concretos para el usuario están en `pasos_gcp.md`.
