# Primera tarea: paper reproducible sobre SHAP

Este paquete implementa un experimento completo y reproducible de explicabilidad en
clasificación de imágenes. Entrena un Random Forest sobre `sklearn.datasets.load_digits`,
explica tres imágenes con TreeSHAP y contrasta las atribuciones mediante una prueba de
eliminación contra máscaras aleatorias tomadas entre píxeles variables.

## Pregunta explicativa

> Para tres casos seleccionados mediante criterios preespecificados, ¿qué píxeles aumentan o
> reducen la probabilidad de la clase predicha y, al sustituir los píxeles con mayor
> SHAP positivo, disminuye esa probabilidad más que al sustituir píxeles al azar?

## Entregables

- `paper.tex` y `paper.pdf`: artículo y versión compilada.
- `src/run_experiment.py`: fuente canónica del experimento y de todas las cifras.
- `notebooks/shap_digits.ipynb`: interfaz reproducible para Jupyter.
- `figures/`: imágenes de prueba y figuras en PNG/PDF.
- `results/`: métricas JSON/CSV, macros LaTeX y modelo serializado.
- `references.bib`: bibliografía.
- `prompts/prompt_log.md` y `LIMITATIONS.md`: trazabilidad y límites.
- `src/validate_outputs.py`: controles automáticos del paquete.
- `build_submission.ps1`: genera un ZIP con una lista explícita de entregables.

## Reproducir en Windows

Requisitos externos: Python 3.11 de 64 bits y una distribución LaTeX con `latexmk`
(TinyTeX, TeX Live o MiKTeX). Desde PowerShell, en esta carpeta:

```powershell
powershell -ExecutionPolicy Bypass -File .\reproduce.ps1
```

La primera ejecución necesita acceso a Internet para instalar las dependencias y puede
usar aproximadamente 0.5--0.8 GB de disco; los datos y pesos no se descargan. El script
crea `.venv`, instala las dependencias directas con versiones verificadas, ejecuta el
notebook, compila el paper y valida el resultado. Para reutilizar el entorno ya instalado:

```powershell
.\reproduce.ps1 -SkipInstall
```

También puede ejecutarse por partes:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m ipykernel install --sys-prefix --name shap-repro --display-name "Python (SHAP reproducible)"
.\.venv\Scripts\python.exe -m nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=shap-repro --ExecutePreprocessor.timeout=900 notebooks\shap_digits.ipynb
latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex
.\.venv\Scripts\python.exe src\validate_outputs.py
```

Para abrir el notebook sin mezclar otras instalaciones de Python:

```powershell
.\.venv\Scripts\python.exe -m jupyterlab notebooks\shap_digits.ipynb
```

Después de validar y personalizar la autoría, genere el archivo de entrega con:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_submission.ps1
```

El ZIP queda en `.dist/Tarea_1_SHAP_reproducible.zip` e incluye un manifiesto SHA-256.

## Antes de entregar

1. Reemplazar `Nombre del estudiante` en la macro `\StudentName` de `paper.tex`.
2. Leer el paper completo y comprobar que su interpretación coincide con las figuras.
3. Ejecutar `reproduce.ps1` en limpio.
4. Consultar las políticas del curso sobre declaración de asistencia con IA y adaptar
   la sección de trazabilidad si fuera necesario, sin ocultar el uso real.

## Decisiones de reproducibilidad

- No se descargan datos ni pesos.
- La división, el modelo, el fondo SHAP, la selección de casos y los controles usan
  semillas fijas.
- Los empates de selección se resuelven por el menor índice original y el control
  aleatorio excluye píxeles constantes en el fondo SHAP.
- Los casos se seleccionan por reglas declaradas, no por apariencia de los mapas.
- El paper importa métricas y filas de tablas generadas por el script.
- Se comprueba fuga entre particiones, normalización de probabilidades, forma de SHAP,
  aditividad, integridad del PDF y referencias LaTeX.

Los resultados son deterministas salvo diferencias numéricas menores entre plataformas
o versiones distintas de las dependencias. Consulte `LIMITATIONS.md` antes de formular
afirmaciones más amplias.
