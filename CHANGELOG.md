# Registro de cambios

## 2026-10-20

- Se añadieron respuestas automáticas de texto con AI Horde cuando Gemini devuelve error 429 por cuota agotada. La cola se consulta en segundo plano; la respuesta alternativa mantiene el idioma del usuario e indica que no tiene búsqueda web en tiempo real.
- Se añadió búsqueda fundamentada de Google para las respuestas de Gemini y se muestran las fuentes consultadas.
- Se amplió la búsqueda automática de imágenes con Openverse y Wikimedia Commons, pasando por varias opciones y continuando si una miniatura no carga.
- Se quitó el botón «Generar con IA» del panel de conversación; la imagen relacionada se busca automáticamente.

## 2026-10-19

- Se añadió búsqueda automática de imágenes en Wikimedia Commons tras cada respuesta: la app guarda una miniatura local y muestra título, autor, licencia y enlace a la fuente. La generación con proveedores queda bajo el botón manual «Generar con IA».
- La búsqueda empieza al enviar la pregunta y prueba términos clave y variantes comunes (por ejemplo, «Formula One», «Formula 1» y «F1») cuando la consulta está en español. Se añadieron reintentos breves para errores temporales 502/503/504 de Gemini.
- Se corrigió la variante mal escrita «cormula» mediante normalización aproximada. Los errores 429 de cuota de Gemini ahora se muestran como aviso breve, con tiempo de espera aproximado, en lugar del bloque técnico completo.
- Se actualizaron la carpeta y el ZIP listos para GitHub para que coincidan con el código y la documentación actuales; se conservaron sin modificar las copias históricas.
- Se unieron Chat e Imágenes en la vista única «Estudio IA»: cada respuesta de Gemini inicia una imagen contextual, con una cola para no ejecutar varias generaciones a la vez. La lectura de texto con dron y dictado permanecen en la misma vista.
- Se retiraron de la interfaz la pestaña Audio, la generación WAV independiente y el gráfico de forma de onda; se conserva Leer respuesta con voz de Windows y el dron animado.
- Se redistribuyó la vista en conversación e imagen relacionada, con el campo y los controles de consulta en la parte inferior.
- Se reorganizó la entrada del Chat para dejar el campo de texto en una fila y distribuir Enviar, Dictar, Leer respuesta y Detener voz en una fila propia.
- Se preparó `ima_diseño/dron_leer_transparente.png` conservando el original. La lectura de respuestas usa el recorte transparente, entra desde el borde y anima el núcleo y los anillos rojos al ritmo de la voz.
- El campo de texto del panel Audio ahora ocupa el espacio vertical disponible; el visualizador y sus controles permanecen agrupados en la parte inferior.
- Se reforzó `.gitignore` para excluir claves, archivos `.env`, copias locales, cachés, modelos Vosk y medios generados.

