---
title: Investigación sobre Jev para el rediseño del Proyecto 2
subtitle: AI News (ai-assisted-news-app) · consulta sobre una noticia
author: Gustavo Cruz 22779 · Mathew Cordero 22982
date: 30 de septiembre de 2026
header-includes:
  - \usepackage{sectsty}
  - \allsectionsfont{\mdseries\sffamily}
---

# Alcance

Documento de apoyo al board. Responde las tres preguntas de la parte 1 de la tarea para el flujo de consulta sobre una noticia. Cada dato lleva una de tres marcas:

- Verificado: leído en la documentación o en las políticas originales de TypeSafe u OpenAI.
- Proveedor: afirmación de TypeSafe sin método o datos que podamos revisar.
- Supuesto: estimación nuestra que falta medir.

# Estado actual del Proyecto 2

Revisado en el repositorio ai-assisted-news-app, rama main.

- El frontend es una app Expo con login de Google o invitado y un feed con tres noticias de demostración (`frontend/src/services/newsService.ts`). No tiene pantalla de chat.
- El backend `backend/assistant` expone `POST /chat`. Recibe `message`, `user_id` y `previous_response_id`.
- Con `user_id`, lee de MongoDB la proyección `assistant_contexts`: nombre, locale, zona horaria, temas preferidos y artículos guardados. Ese contexto viaja a OpenAI en cada turno.
- El proveedor usa gpt-5-mini por la Responses API con `store=true`, razonamiento bajo y hasta 1600 tokens de salida.
- El prompt `prompts/system.md` sigue siendo el del asistente financiero NOVU.
- Toda pregunta, incluida una fecha o una fuente, pasa por el LLM. La respuesta es texto libre sin cita y sin señal de incertidumbre.

# 1. Qué puede resolver Jev y sus límites frente a un LLM

Jev es el primer modelo System One de TypeSafe. La versión vigente es jev-1.13.0. (Verificado)

Recibe un estado (texto, objeto JSON o arreglo de textos) y un conjunto de preguntas tipadas. Responde todas en paralelo en una sola llamada a `POST /v1/systemone`. (Verificado)

| Primitiva | Qué responde | Salida |
|---|---|---|
| Choice | Cuál opción de una lista aplica | opción, probabilidad por opción, confianza |
| Score | Qué nivel de una rúbrica corresponde | nivel, probabilidad por nivel, confianza |
| Noul | Probabilidad de que una afirmación sea verdadera | valor entre 0 y 1 |

Tareas que encajan en nuestro flujo:

- Clasificar la intención de una pregunta (Choice).
- Elegir el párrafo de la noticia que responde (Choice sobre párrafos numerados).
- Verificar si la noticia contiene la respuesta (Noul).
- Detectar preguntas fuera de alcance o de consejo sensible (Noul).

Límites que TypeSafe documenta para jev-1.13 (Verificado):

- No genera texto, no conversa y no escribe código. Para redactar recomienda un modelo generativo.
- No cuenta de forma confiable ni hace aritmética.
- Compara mal fechas; recomienda extraer componentes y calcular en código.
- Lee las instrucciones de forma literal.
- Pierde precisión con estados grandes llenos de detalle irrelevante.
- El contenido adversarial dentro del estado puede mover la respuesta.
- No garantiza consistencia entre preguntas equivalentes formuladas distinto.
- Sólo acepta texto; 64k tokens por solicitud y 32k para el estado más la pregunta más larga.
- El idioma principal de entrenamiento es inglés. Otros idiomas funcionan con menor precisión y TypeSafe pide probar con contenido propio.

La confianza resume la forma de la distribución de probabilidades. TypeSafe sugiere tres rangos: actuar, confirmar o no actuar, con umbrales según el riesgo de cada acción. La calibración se mide sobre grupos de predicciones y no garantiza que una respuesta individual sea correcta. (Verificado)

Frente a un LLM, Jev cambia flexibilidad por respuestas acotadas. Un LLM redacta, combina información de varias partes y conversa. Jev sólo elige entre opciones definidas por nosotros, con probabilidad y confianza.

# 2. Datos que enviaríamos y políticas de TypeSafe

Datos que saldrían hacia TypeSafe en cada pregunta libre:

- Texto de la pregunta, después de quitar correos, teléfonos y números de DPI en código.
- Título y párrafos numerados de la noticia, que es contenido público.
- Las preguntas tipadas y sus opciones.

No saldrían `user_id`, nombre, correo, temas preferidos, artículos guardados ni historial.

Políticas revisadas:

- Entrenamiento: la política de privacidad dice que no entrenan ni ajustan modelos de IA con el input y que no lo divulgan a terceros salvo proveedores de servicio. La página de modelos repite que Jev no se entrena con solicitudes ni respuestas de clientes. (Verificado)
- Conservación: guardan datos personales mientras sea razonablemente necesario para dar el servicio o para fines comerciales. No hay plazo fijo. La retención cero está disponible sólo para clientes empresariales. (Verificado)
- Encargado de tratamiento: el DPA define al cliente como responsable y a TypeSafe como encargado. Se compromete a no vender datos y a procesarlos según instrucciones documentadas. Publica una lista de subencargados y avisa antes de agregar uno. (Verificado)
- Ubicación: el servicio está alojado en Estados Unidos. (Verificado)
- Telemetría: el sitio usa cookies, Google Analytics y registra IP, dispositivo, navegador y horarios de uso. No encontramos qué registra la API por cada solicitud ni si el SDK envía telemetría. (Supuesto, falta verificar)
- Términos de uso del sitio: piden no enviar información confidencial por el sitio y limitan la responsabilidad a US$100. El uso por API se rige por el Master Customer Agreement, que no revisamos a fondo. (Verificado / falta verificar)
- Acceso: Jev está en acceso temprano con lista de espera. Los límites de uso cambian sin aviso por la demanda. (Verificado)

# 3. Evidencia sobre velocidad, costo y recursos

| Dato | Valor | Marca |
|---|---|---|
| Precio Jev | US$0.042 por millón de tokens de entrada; salida sin costo | Verificado |
| Precio gpt-5-mini | US$0.25 entrada, US$2.00 salida por millón | Verificado |
| Límites Jev | 100k tokens/s y 40 solicitudes/s, ajustables sin aviso | Verificado |
| Velocidad frente a LLM | 193.6x más rápido, 0.114 s frente a 8.566 s | Proveedor |
| Costo frente a LLM | 444.6x más barato | Proveedor |
| Preguntas en lote | 13 preguntas en una llamada: 0.27 s y US$0.0005; 13 llamadas: 2.71 s y US$0.0061 | Proveedor |
| Cero alucinaciones | Cierto en el sentido de que sólo elige opciones dadas; puede elegir mal | Proveedor |
| Consumo de energía o hardware | No publicado | Falta verificar |
| Tokens por turno en AI News | 2000 de entrada y 400 de salida con el LLM; 1500 de entrada con Jev | Supuesto |
| Proporción de preguntas resolubles sin LLM | 60% | Supuesto |

Las cifras de velocidad del proveedor vienen de pruebas internas en tareas System One sin método publicado. No hay benchmarks independientes.

Estimación por 1000 preguntas (Supuesto):

| | Actual | Propuesto |
|---|---|---|
| Llamadas a gpt-5-mini | 1000 | 400 |
| Costo LLM | US$1.30 | US$0.44 |
| Llamadas a Jev | 0 | 1000 |
| Costo Jev | US$0 | US$0.06 |
| Total | US$1.30 | US$0.50 |

En recursos, Jev y gpt-5-mini corren en la infraestructura de cada proveedor. Para AI News el cambio es menos tokens procesados por LLM y lógica determinista en el contenedor FastAPI, con costo de cómputo despreciable. El consumo energético real no se puede comparar con la información publicada.

# Pendiente de verificar

- Latencia real de Jev desde Guatemala y precisión con preguntas en español guatemalteco, con el Playground.
- Qué registra la API por solicitud y por cuánto tiempo.
- Cláusulas del Master Customer Agreement sobre datos enviados por API.
- Distribución real de preguntas y tokens por turno, con registros de uso.

# Fuentes

Consultadas el 30 de septiembre de 2026.

- Introducción a Jev: <https://docs.typesafe.ai/introduction>
- System One: <https://docs.typesafe.ai/concepts/system-one>
- Estado: <https://docs.typesafe.ai/concepts/state>
- Modelos, precio, límites e idiomas: <https://docs.typesafe.ai/models>
- Límites de jev-1.13: <https://docs.typesafe.ai/model-jaggedness/jev-1.13>
- Confianza: <https://docs.typesafe.ai/confidence>
- Jev con agentes de código: <https://docs.typesafe.ai/introduction/coding-agents>
- Preguntas en paralelo: <https://docs.typesafe.ai/cookbooks/parallel_questions>
- Legal y retención cero: <https://docs.typesafe.ai/legal>
- Política de privacidad: <https://typesafe.ai/legal/privacy-policy>
- Data Processing Agreement: <https://typesafe.ai/legal/data-processing>
- Términos de uso: <https://typesafe.ai/legal/terms>
- Sitio de TypeSafe y afirmaciones de rendimiento: <https://typesafe.ai>
- Modelo gpt-5-mini y precio: <https://developers.openai.com/api/docs/models/gpt-5-mini>
- Código del Proyecto 2: `backend/assistant` y `frontend` en ai-assisted-news-app
