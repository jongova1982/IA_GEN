# JonGoX IA Gen - versión web local

Esta versión web se ejecuta en Windows con FastAPI y Ollama. El chat genera la respuesta de texto localmente. La búsqueda web está activa por defecto: consulta DuckDuckGo para obtener fuentes y Openverse para encontrar hasta cuatro imágenes relacionadas, con enlace de origen y datos de autoría/licencia cuando están disponibles. Puedes desactivar la casilla para conversar solo con el modelo local.

La búsqueda de imágenes usa el catálogo abierto de Openverse y no necesita cuenta. Requiere conexión a internet y puede tener límites temporales. Al buscar, la consulta se envía a DuckDuckGo y Openverse. Revisa la licencia en la página de origen antes de reutilizar una imagen.

El botón **Crear imagen** y las solicitudes como **genera una imagen de...** usan Pollinations desde el navegador. El servicio clásico es gratuito y no requiere clave, aunque puede limitar el uso. Las solicitudes se envían a Pollinations. Los sprites animados y el logo se sirven desde los recursos locales del proyecto.

## Iniciar en Windows

Desde PowerShell, en la carpeta del proyecto:

```powershell
ollama pull llama3.2:1b
py -m pip install -r requirements-web.txt
py -m uvicorn web_app:app --host 127.0.0.1 --port 8000
```

Abre <http://127.0.0.1:8000> y deja Ollama abierto. Para detener el servidor, usa `Ctrl+C` en PowerShell.

Para seleccionar otro modelo, define `OLLAMA_MODEL` antes de iniciar Uvicorn. Por ejemplo:

```powershell
$env:OLLAMA_MODEL = "llama3.2:1b"
py -m uvicorn web_app:app --host 127.0.0.1 --port 8000
```

## Archivos web

- `web_app.py`: servidor FastAPI, conexión con Ollama y búsqueda web.
- `static/index.html`: interfaz.
- `static/styles.css`: diseño adaptable.
- `static/app.js`: chat, galería de imágenes, lectura y generación de imágenes.
- `static/mascot-01.webp` a `mascot-04.webp`: cuadros del sprite animado.
- `requirements-web.txt`: dependencias web; no reemplaza `requirements.txt` de escritorio.

La versión de escritorio sigue disponible con `py app.py` y conserva sus propios requisitos.
