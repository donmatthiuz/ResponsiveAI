# Capturas incluidas en el reporte del README

Encabezado: Mathew Alexander Cordero Aquino - 22982
Repositorio: https://github.com/donmatthiuz/ResponsiveAI/tree/labmonitoring

Corrida: official-20261031T025905Z
Ventana medida: 30 de octubre de 2026, 21:01:22 a 22:01:22 (Guatemala, UTC−6).
Primero aplicar la propuesta en rendered/dashboard.json y seleccionar un intervalo visual que cubra todos los minutos de esa hora.

Guardar aquí imágenes PNG legibles del mismo dashboard:

1. 01_metricas_nativas.png: solicitudes por minuto/clase HTTP y latencias nativas p50/p95.
2. 02_metricas_logs.png: resultados por categoría y latencia p95 por operación/segmento.
3. 03_sql.png: tasas de errores por categoría y latencias SQL por segmento/operación/percentil.
4. 04_logs_correlacion.png: panel Eventos API con un evento expandido; debe verse request_id,run_id,status_code,error_type y atributos de negocio.

Ejemplo real de 500 para la cuarta captura:
request_id=official-20261031T025905Z-request-000009
run_id=official-20261031T025905Z
error_type=simulated_failure

Mantener visible el título del dashboard y el intervalo de tiempo. Si no cabe una fila de gráficas, usar imágenes adicionales con sufijos a/b. No son necesarias capturas de credenciales, login ni IAM.
