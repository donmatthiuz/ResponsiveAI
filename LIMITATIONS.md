# Limitaciones y uso responsable

## Alcance de los datos y del modelo

- `digits` tiene solo 1,797 imágenes monocromáticas de 8×8 píxeles. Es adecuado para
  una demostración reproducible, pero no representa sistemas modernos de visión.
- El Random Forest trata cada píxel como un atributo tabular y no incorpora estructura
  espacial explícita, invariancia a traslación ni conocimiento del trazo.
- Sus probabilidades son promedios de las probabilidades estimadas por los árboles y no
  fueron calibradas. Deben
  llamarse “salidas” o “confianzas del modelo”, no probabilidades empíricas garantizadas.

## Límites de SHAP

- Una atribución explica la salida del modelo; no demuestra qué “ve” una persona ni
  establece causalidad.
- Los valores dependen del conjunto de fondo estratificado y del supuesto
  `interventional`. Otro fondo puede cambiar magnitudes e incluso signos.
- Los píxeles vecinos están correlacionados. La perturbación interventional rompe esas
  dependencias para definir la explicación, lo que condiciona su interpretación.
- La aditividad verifica que las atribuciones reconstruyen la salida respecto a la
  referencia; no garantiza que la explicación sea semánticamente correcta.
- Los mapas de color pueden parecer segmentaciones, pero cada celda es una contribución
  numérica para una clase particular.

## Límites de la prueba de eliminación

- Sustituir píxeles por medias puede crear imágenes fuera de la distribución original.
- Comparar con máscaras aleatorias mide sensibilidad local del modelo fijo, no una
  intervención causal sobre el objeto representado.
- Aunque excluye los píxeles constantes en el fondo SHAP, el control uniforme puede
  elegir atributos de aporte pequeño o negativo. El porcentaje de victorias observado
  solo es válido frente a ese control, no como fidelidad general.
- No se reentrena el clasificador después de eliminar información; por ello el protocolo
  no equivale a ROAR (“Remove And Retrain”).
- El intervalo bootstrap es descriptivo y condicional a una sola partición, semilla,
  referencia y realización de máscaras. No incorpora variación por reentrenamiento ni
  garantiza generalización a otras poblaciones.
- La evaluación global se restringe a predicciones correctas porque busca perturbar
  evidencia de una clase acertada. Los errores se estudian solo entre los tres casos.

## Selección, generalización y herramientas

- Tres imágenes permiten una auditoría detallada, pero no resumen todo el conjunto.
  Las reglas deterministas reducen selección oportunista, no eliminan el sesgo de la
  definición de los criterios de selección.
- La semilla fija mejora repetibilidad, pero una sola partición no mide variación entre
  particiones. Validación cruzada queda fuera del alcance de esta primera tarea.
- Las dependencias directas tienen versiones fijadas en `requirements.txt`, pero no se
  distribuye un *lockfile* completo de cada dependencia transitiva. Otras versiones de
  SHAP han usado formas de salida diferentes. El código las normaliza, pero la
  combinación verificada es la documentada.
- El texto y el código tuvieron asistencia de IA. Una persona debe revisar resultados,
  cumplir las reglas académicas aplicables y asumir responsabilidad por la entrega.
