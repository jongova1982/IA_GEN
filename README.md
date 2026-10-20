# JONGOX IA GEN

Aplicación de escritorio para Windows creada con Python y Tkinter. En una sola vista reúne chat con Gemini, imágenes automáticas, dictado local y lectura en voz alta.

## Funciones

- **Conversación e imágenes web:** consulta Gemini Flash con búsqueda fundamentada de Google para investigar respuestas informativas y muestra las fuentes web al final de la respuesta. Si Gemini agota la cuota, solicita automáticamente una respuesta de texto a AI Horde en segundo plano; la cola anónima puede tardar y esa respuesta no incluye búsqueda web en tiempo real. En paralelo busca una imagen relacionada en Openverse y, si no encuentra una, prueba Wikimedia Commons. Guarda la imagen localmente y muestra título, autor, licencia y enlace a la página de origen. La miniatura puede ampliarse con el cursor o con un clic.
- **Generación de imágenes:** la imagen de cada respuesta se busca automáticamente en Openverse y, como respaldo, en Wikimedia Commons, sin pulsar un botón. La pestaña **Imágenes** conserva el generador manual con Pollinations (si hay clave configurada) y AI Horde como alternativa; Pollinations puede consumir créditos y AI Horde puede tener cola.
- **Dictado y lectura:** transcribe ocho segundos de voz localmente con Vosk. **Leer respuesta** usa una voz instalada en Windows; muestra el dron recortado con fondo transparente entrando desde el borde y pulsa su núcleo rojo al ritmo de las palabras. **Detener voz** corta la lectura.
- **Diseño:** Chat e imagen se muestran juntos en una sola vista, con el campo de pregunta y sus controles abajo. Se conserva el fondo superior, el sprite animado, el logo y las líneas rojas laterales.
- **Borrar chat:** limpia la conversación, la imagen visible y los trabajos de imagen que aún esperan turno. Una generación ya iniciada puede terminar en segundo plano; los archivos guardados se conservan.

La aplicación requiere conexión a internet para Gemini, AI Horde, Openverse y Wikimedia Commons. La generación manual de imágenes requiere conexión a Pollinations o AI Horde. El dictado y la voz local requieren sus modelos o componentes instalados.

Los errores temporales 502, 503 y 504 de Gemini se reintentan brevemente. Si el proveedor continúa saturado, la respuesta puede seguir fallando; la búsqueda de imagen se ejecuta de forma independiente.

Cuando Gemini devuelve 429 por cuota agotada, la app pide una respuesta de texto a AI Horde automáticamente. El acceso anónimo es gratuito, puede tener una cola larga o estar limitado, y no ofrece búsqueda web en tiempo real.

## Requisitos

- Windows y Python 3.10 o posterior.
- Una clave de Google AI Studio para el chat.
- Una clave de Pollinations es opcional. Solo se usa al generar manualmente desde la pestaña **Imágenes**; esa cuenta puede consumir créditos.
- AI Horde ofrece generación de texto e imágenes; sin clave usa acceso anónimo y puede tener cola de espera.
- El modelo Vosk en `models/vosk-model-small-es-0.42` o en la raíz del proyecto para usar dictado.

## Claves

Guarda cada clave sola en una línea, junto a `app.py`. No las publiques ni las compartas.

| Servicio | Archivo | Variable de entorno |
| --- | --- | --- |
| Google AI Studio | `gemini_api_key.txt` | `GEMINI_API_KEY` |
| Pollinations (opcional) | `pollinations_api_key.txt` | `POLLINATIONS_API_KEY` |
| AI Horde (opcional) | `aihorde_api_key.txt` | `AI_HORDE_API_KEY` |

Al pulsar **Generar con IA**, si Pollinations no está configurado, la app usa AI Horde. Si Pollinations falla por un error, también intenta AI Horde. Cuando Pollinations tarda demasiado, la app no repite la solicitud ni inicia otra automáticamente, porque la primera podría haberse completado y consumido créditos.

## Instalación e inicio

Desde PowerShell:

```powershell
cd C:\IA_GEN
py -m pip install -r requirements.txt
py app.py
```

## Comprobaciones

Las pruebas unitarias usan datos locales y respuestas simuladas; no envían solicitudes a Gemini, Pollinations o AI Horde ni leen el contenido de las claves:

```powershell
cd C:\IA_GEN
py -m unittest discover -s tests -v
py -m py_compile app.py
```

## Archivos del proyecto

- Imágenes generadas: `generated_images`
- Audios WAV: `generated_audio`
- Fondos, logo y sprites: `ima_diseño`
- Código principal: `app.py`
- Pruebas locales: `tests/test_app.py`
- Historial de cambios: `CHANGELOG.md`

Los archivos de claves, modelos Vosk, imágenes generadas y audios están excluidos del control de versiones mediante `.gitignore`.
