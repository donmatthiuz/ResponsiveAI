# Decisiones y ajustes respecto al PDF

La especificación de detalle es `INSTRUCCIONES_AGENTE.md`; el PDF original permanece intacto. No se modificaron ni recuperaron eliminaciones previas del usuario.

| Decisión | Motivo y consecuencia |
| --- | --- |
| Python 3.13.15 local; runtime `python313` | Se probó el intérprete de la versión requerida, aunque el Python del sistema es 3.14.8. Dependencias exactas en `requirements-lock.txt`. |
| Firestore nativo, base dedicada `lab-orders` | Estado compartido entre procesos/instancias. `lab_runs/{run_id}/orders/{id}` aísla corridas. El SDK recibe proyecto/base por entorno. |
| Cancelación transaccional | Revalida estado dentro de la transacción; dos clientes producen un solo cambio. Lectura previa permite respetar 404/409 antes de decidir una falla artificial. |
| `amount` persistido como double | El contrato acepta números finitos positivos. Convertir enteros evita el límite signed64 de Firestore para entradas grandes; no se promete precisión decimal monetaria. NaN, infinitos y booleanos se rechazan. |
| Logging centralizado en `finally` | Un evento por llamada atendida, incluso 4xx/5xx. Rutas normalizadas evitan cardinalidad por IDs. Excepciones exponen solo nombre de clase en el log y mensaje genérico al cliente. |
| `phase` añadido al log | Preparación y tráfico comparten run_id para poder leer sus pedidos; SQL filtra `phase='traffic'`. Los IDs preparatorios tienen prefijo separado y nunca entran al CSV medido. |
| Normal truncada por rechazo NumPy | Se genera y descarta fuera de [0,60], sin acumular muestras en extremos. Semilla, configuración, versión NumPy y plan quedan guardados. |
| Inválidas ajustan operación | Los tipos 400/404/409 se seleccionan equiprobablemente, con operación adecuada. La mezcla final puede variar respecto a la base 50/30/20 de eventos válidos. |
| Preparación con TaskGroup y máximo tres intentos | Se cancela la preparación si cualquier recurso queda incompleto. Aleatoriedad del plan no se usa en reintentos. IDs asignados por backend no alteran el calendario. |
| Quietud de 120 s en ejecuciones con escala 1 | Fuera de la hora medida, después de preparar. Separa preparación de las agregaciones nativas de 60 s. Pruebas aceleradas no esperan esos 120 s. |
| Reloj monotónico y tareas independientes | Despacha sin esperar la respuesta anterior; UTC solo sirve para correlación. Si vence la ventana por suspensión/saturación, no envía el resto y registra `send_window_expired`. |
| Registro CSV serial y flush por fila | No hay await entre escribir y flush, por lo que un bucle de eventos serializa escrituras. Ctrl+C drena cancelaciones y escribe resumen incompleto. Pérdida abrupta del sistema requiere recuperación desde CSV. |
| CLI autenticada opcional | `--auth gcloud` obtiene y renueva ID tokens cada 40 min. Impersonación opcional permite audiencia explícita. No hay claves ni tokens en archivos de evidencia. |
| Proveedores acotados y fijados | Google `~>6.0` → 6.50.0 y archive `~>2.4` → 2.8.1 en lockfile. Terraform usado 1.13.5; despliegue mínimo 1.5, pruebas mock mínimo 1.7. |
| Output URL corregido | El PDF usa `.url`; se usa `service_config[0].uri`, admitido por el esquema validado. IAM utiliza el nombre del servicio obtenido de `service_config[0].service`, no una suposición sobre el nombre de función. |
| Fuentes ZIP filtradas y con hash | `.build/.gitkeep` conserva el directorio; se excluyen cachés. Se inspeccionó el ZIP y solo contiene código, `__init__.py` y dependencias. El hash cambia al cambiar fuentes. |
| Repositorio propio de Artifact Registry | Hace explícitos el destino de imágenes, los permisos del build y el alcance de limpieza. Evita gestionar el repositorio compartido `gcf-artifacts`. |
| IAM de build y runtime separados | Se conservan roles del PDF. Build agrega objectViewer para fuentes/staging y writer sobre el repositorio propio. Runtime agrega datastore.user. No se autoasignan privilegios a la identidad que despliega. |
| APIs adicionales | Firestore para persistencia; Cloud Resource Manager y Service Usage para administración de IAM y APIs del proyecto. |
| Firestore con `deletion_policy=DELETE` | El valor predeterminado del proveedor abandona datos; aquí la base dedicada debe eliminarse en el cierre. No importar una base compartida sin inspección. |
| `_Default` y APIs persisten | Analytics y retención quedan en el bucket automático; destroy no los revierte. APIs tienen disable_on_destroy=false. Residuos de GCF se inspeccionan después. |
| Métricas con etiquetas acotadas | Contador: outcome/category/endpoint/customer_tier. Distribución: endpoint/customer_tier. Sin run_id/request_id/order_id como etiquetas. Buckets ms: 0,1,5,10,25,50,100,250,500,1000,2500,5000,10000,30000,60000, con underflow/overflow. |
| Un dashboard, ocho widgets | Cuatro paneles de métricas, dos SQL, uno de logs y uno de instrucciones. Percentiles de distribuciones: ALIGN_SUM y REDUCE_PERCENTILE para combinar distribuciones; no promedio de percentiles de instancias. |
| SQL mediante REST preview | Se consultó el discovery real de Monitoring y se guardó el subesquema Dashboard. El SDK estable 2.22.0 no incluye opsAnalyticsQuery; las pruebas validan métricas/logs contra el SDK y el dashboard completo contra REST. |
| Terraform envía JSON de dashboard sin SDK tipado | Se revisó el código del proveedor 6.50.0: usa un mapa JSON y REST. El uso de campos preview sigue requiriendo comprobación real en el proyecto. Hay fallback por consola documentado. |
| SQL con filtros propios | Vista global del PDF, run_id, fase, servicio y timestamps explícitos; JSON_VALUE/SAFE_CAST, SAFE_DIVIDE y cuantiles aproximados. Inicio: t0; fin: respuestas drenadas. Native/log metrics usan la misma ventana UTC. |
| Preservar cambios manuales | `dashboard_override_file` permite administrar el JSON exportado real. Se exporta de nuevo tras agregar widgets por consola para que otro apply los conserve. |

## Fuentes oficiales consultadas

- [Runtimes Python](https://docs.cloud.google.com/functions/docs/runtime-support).
- [Esquema Terraform Gen2](https://raw.githubusercontent.com/hashicorp/terraform-provider-google/main/website/docs/r/cloudfunctions2_function.html.markdown).
- [Terraform Firestore y política de borrado](https://registry.terraform.io/providers/hashicorp/google/6.50.0/docs/resources/firestore_database).
- [Build de funciones](https://docs.cloud.google.com/functions/docs/building).
- [Emulador Firestore](https://docs.cloud.google.com/firestore/native/docs/emulator).
- [Transacciones de Firestore](https://docs.cloud.google.com/firestore/native/docs/manage-data/transactions).
- [Dashboard REST, agregaciones y SQL](https://docs.cloud.google.com/monitoring/api/ref_v3/rest/v1/projects.dashboards).
- [Discovery REST usado para validación](https://monitoring.googleapis.com/$discovery/rest?version=v1).
- [Código del proveedor de dashboard 6.50.0](https://raw.githubusercontent.com/hashicorp/terraform-provider-google/v6.50.0/google/services/monitoring/resource_monitoring_dashboard.go).
- [Ejemplos del esquema SQL de Analytics](https://docs.cloud.google.com/logging/docs/analyze/examples).
- [Gráficas SQL en dashboards](https://docs.cloud.google.com/logging/docs/analyze/charts).

La comprobación de documentación/esquema no equivale a validación de los recursos desplegados.

## Ajuste tras el smoke real

El usuario confirmó una gráfica SQL de errores creada desde Analytics y guardada en el dashboard. Su JSON real está en `evidence/smoke-20261031T020723Z/dashboard.json`. La configuración difiere de la plantilla inicial en los campos de desglose: límite positivo, función count para selección de series y orden descendente; la dimensión incluye sortColumn/sortOrder explícitos. La medida sigue usando none porque SQL ya agrupa por minuto. Se trasladan esos ajustes a ambos paneles de la plantilla. No se aisló un único campo como causa; el conjunto se basa en la configuración observada funcionando.

El fixture `tests/fixtures/sql_chart_verified.json` conserva esa referencia; las pruebas comprueban correspondencia de parámetros y que el render no altere widgets manuales al actualizar nuestras consultas. La propuesta `dashboard.smoke-review.json` mantiene los nueve widgets, incluida la referencia manual. No es una exportación final validada: hay que revisar el plan, aplicarlo y comprobar la latencia SQL en el dashboard.

### Segunda revisión del panel de latencia

Tras aplicar el primer ajuste, el usuario confirmó por captura que el SQL original de errores muestra las tres categorías. La latencia seguía vacía con dos datasets/medidas y dos desgloses. La [guía de Analytics](https://docs.cloud.google.com/logging/docs/analyze/charts#add_a_breakdown) restringe las gráficas con varias medidas y desglose. Como alternativa compatible con la gráfica verificada, la consulta de latencia calcula p50/p95 por grupo y genera dos filas, con `percentile`, `latency_ms` y una etiqueta de serie que combina segmento/endpoint/percentil. El widget usa una sola medida y un desglose acotado a100 series. `requests` se repite por percentil; no sumar ambas filas para obtener el volumen.

El renderer migra también exportaciones anteriores con medidas p50_ms/p95_ms al formato nuevo y conserva los widgets manuales. Cinco pruebas locales pasan, incluida esa migración. La consulta real se prepara en `evidence/smoke-20261031T020723Z/latency-review/latency_by_tier.sql`; todavía debe ejecutarse y comprobarse en GCP antes de concluir que el panel está corregido.
