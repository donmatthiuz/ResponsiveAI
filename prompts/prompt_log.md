# Registro de prompts, decisiones y verificaciones

Fecha de trabajo: 4 de septiembre de 2026.

Este registro distingue el pedido textual del usuario de las instrucciones de trabajo
empleadas para construir el paquete. No pretende reproducir razonamiento interno del
modelo ni inventar conversaciones que no ocurrieron.

## 1. Pedido original

**Usuario:** “me puedes ayudar a generar esta primera tarea”, acompañado de una foto
de la diapositiva “Primera tarea: un paper LaTeX reproducible sobre SHAP”.

La diapositiva se interpretó como estos requisitos:

- clasificador de imágenes preentrenado o propio;
- entre una y tres imágenes de prueba;
- una pregunta explicativa concreta;
- ciclo de definir estructura, generar `.tex`, compilar, ejecutar SHAP, insertar
  resultados y revisar afirmaciones;
- paquete con `paper.tex` + PDF, código/notebook, figuras/referencias y registro de
  prompts + limitaciones.

## 2. Prompt de diseño usado con el asistente

> Diseña un caso académicamente sólido, reproducible en Windows y ejecutable en CPU
> para explicar entre una y tres imágenes con SHAP. Debe evitar descargas innecesarias,
> formular una pregunta concreta, especificar selección no oportunista de ejemplos,
> producir figuras y añadir una comprobación cuantitativa de sensibilidad vinculada
> con la fidelidad local.

**Decisión resultante:** conjunto `load_digits`, Random Forest propio, TreeSHAP, tres
casos deterministas y prueba de eliminación frente a píxeles al azar.

## 3. Prompt de implementación usado con el asistente

> Implementa un script canónico que entrene el modelo con semilla fija, compruebe la
> separación de datos, calcule TreeSHAP en probabilidad con un fondo estratificado,
> verifique aditividad, exporte métricas/figuras/tablas y falle con un mensaje claro si
> se rompe una invariante. Genera también un notebook delgado que llame al mismo código.

**Salidas:** `src/run_experiment.py`, `notebooks/shap_digits.ipynb`, `figures/` y
`results/`.

## 4. Prompt de redacción usado con el asistente

> Redacta en español un paper LaTeX autocontenido. Distingue fidelidad, sensibilidad y
> causalidad; no conviertas mapas SHAP en segmentaciones; incluye metodología suficiente
> para reproducir, resultados generados automáticamente, bibliografía primaria,
> limitaciones y declaración transparente de asistencia con IA.

**Salida:** `paper.tex` y `references.bib`.

## 5. Prompt de revisión usado con el asistente

> Ejecuta el experimento y la compilación desde cero; verifica métricas, suma de
> probabilidades, fuga entre particiones, forma del tensor SHAP, aditividad, consistencia
> de tablas, existencia de figuras/PDF y ausencia de referencias LaTeX indefinidas.
> Corrige cualquier fallo encontrado y documenta lo que no pueda garantizarse.

**Evidencia verificable:** consola de `reproduce.ps1`, `results/metrics.json`,
`paper.log` y `src/validate_outputs.py`.

## 6. Cambios que debe hacer la persona autora

- Sustituir el nombre genérico en `paper.tex`.
- Leer y validar las interpretaciones con las figuras regeneradas.
- Adaptar la declaración de IA a la política específica del curso.
- No presentar el intervalo bootstrap ni la prueba de eliminación como causalidad.

Las limitaciones técnicas e inferenciales completas están en `LIMITATIONS.md`.
