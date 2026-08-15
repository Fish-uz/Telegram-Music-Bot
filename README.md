# AllMusic

AllMusic es un bot privado de Telegram que busca música en YouTube, convierte el audio a MP3 y reutiliza los `file_id` de Telegram para entregar solicitudes repetidas sin volver a descargar ni subir el archivo.

Incluye un dashboard administrativo responsivo, estadísticas, historial, administración de usuarios, playlists, enlaces de Spotify/Deezer, top global periódico, ingestor privado y despliegue con Docker.

> Usa AllMusic únicamente con contenido que tengas derecho a descargar y distribuir. Cada plataforma mantiene sus propias condiciones de uso.

## Flujo principal

1. El usuario envía un título, artista o enlace compatible.
2. Un enlace de Spotify o Deezer se convierte en artista y título mediante metadatos públicos. El audio no se extrae de esas plataformas.
3. AllMusic busca resultados equivalentes en YouTube.
4. El usuario elige una pista mediante botones inline.
5. Si existe en caché, Telegram entrega directamente su `file_id`.
6. Si no existe, yt-dlp descarga el audio, FFmpeg lo convierte a MP3 de 192 kbps y el bot lo sube.
7. El nuevo `file_id` se persiste en SQLite para solicitudes futuras.
8. Una barra de progreso real informa cola, descarga, conversión y subida.

## Funciones

- Búsqueda y paginación de resultados de YouTube.
- Resolución inicial de enlaces de Spotify y Deezer sin credenciales obligatorias.
- Playlists de YouTube con límite configurable.
- Caché autorreparable: un `file_id` inválido se elimina y regenera.
- Límite de descargas concurrentes y deduplicación por video.
- Perfil, historial, top global, soporte y menú persistente.
- Panel del propietario, ban, unban y broadcast.
- Top global periódico para usuarios activos.
- SQLite en modo WAL y operaciones transaccionales cortas.
- Registro de fallos y supervisor de actualizaciones de yt-dlp.
- Dashboard AllMusic con resumen, usuarios, biblioteca, actividad y sistema.
- Dockerfile, Compose y healthcheck.

## Requisitos locales

- Python 3.12 recomendado.
- FFmpeg y FFprobe disponibles en `PATH`.
- Node.js 22+ o Deno 2.3+ para los desafíos JavaScript de YouTube.
- Cookies de YouTube exportadas en formato Netscape cuando YouTube solicite autenticación.

Pyrogram funciona sin TgCrypto. No se incluye porque Python 3.12 exige compilarlo localmente; descarga, FFmpeg y subida siguen siendo los factores dominantes de rendimiento.

## Instalación local

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env`:

```env
API_ID=123456
API_HASH=tu_api_hash
BOT_TOKEN=tu_bot_token
OWNER_ID=tu_id_personal
YOUTUBE_COOKIES=youtube_cookies.txt
BACKUP_CHAT_ID=-1001234567890
DASHBOARD_TOKEN=un_token_largo_y_aleatorio
```

Las credenciales `API_ID` y `API_HASH` pertenecen a Telegram; `BOT_TOKEN` se obtiene para el bot y `OWNER_ID` debe ser el ID numérico personal del administrador.

Inicia una sola instancia:

```powershell
python main.py
```

No ejecutes `main.py` y `bot.py` simultáneamente: ambos usarían la misma sesión de Pyrogram.

## Dashboard

Abre `http://localhost:8080`. Si `DASHBOARD_TOKEN` está configurado, el navegador lo solicitará la primera vez y lo almacenará en `localStorage`.

Endpoints principales:

- `GET /api/health`
- `GET /api/stats`
- `GET /api/users`
- `GET /api/users/{id}`
- `POST /api/users/{id}/ban`
- `GET /api/songs`
- `GET /api/history`
- `GET /api/system`

Sin `DASHBOARD_TOKEN`, la API administrativa solo acepta conexiones locales o de redes privadas, incluido el bridge de Docker. Configúralo siempre que publiques el puerto en Internet.

## Docker Desktop

Docker Compose reutiliza `.env`, persiste la base y la sesión de Telegram, y monta las cookies como solo lectura:

```powershell
docker compose build
docker compose up -d
docker compose logs -f allmusic
```

Dashboard: `http://localhost:8080`.

Para detenerlo:

```powershell
docker compose down
```

## Ingestor privado

El ingestor no inicia con el bot. Prepara un TXT con una búsqueda por línea y ejecuta:

```powershell
python ingestor.py downloads\archivostxt\lista.txt
```

Necesita `BACKUP_CHAT_ID`. Usa una sesión independiente y alimenta la misma base de caché. No ejecutes dos ingestas simultáneas.

## Spotify y Deezer

Actualmente los enlaces de pistas funcionan como resolución de metadatos:

- Spotify: endpoint público oEmbed.
- Deezer: endpoint público de información de pista.
- Fuente final de audio: resultado elegido en YouTube.

Las variables de credenciales oficiales ya están reservadas en `.env.example`. Cuando se incorporen sus APIs oficiales podrán añadirse álbumes, playlists privadas y búsquedas más precisas sin cambiar el flujo de descarga.

## Recuperación de yt-dlp

Cuando se acumulan tres fallos técnicos compatibles dentro de treinta minutos —por ejemplo 403, firmas o desafíos del reproductor— el supervisor comprueba una actualización de `yt-dlp`. Solo reinicia el proceso si la versión realmente cambió. Videos privados, eliminados o no disponibles no activan una actualización.

Configurable mediante:

```env
AUTO_UPDATE_YTDLP=true
UPDATE_FAILURE_THRESHOLD=3
```

En producción se recomienda conservar también `restart: unless-stopped` de Docker Compose.

## Pruebas

```powershell
python -m unittest discover -s tests -v
python -m compileall -q main.py bot.py dashboard.py ingestor.py core database handlers services tests
git diff --check
```

Las pruebas cubren persistencia, caché de Telegram, subida simulada, clasificación de actualizaciones y resolución de consultas.

## Logs

AllMusic conserva tres archivos rotativos de hasta 10 MB, con cinco respaldos cada uno:

- `logs/allmusic.log`: actividad útil, búsquedas, descargas, caché y warnings.
- `logs/errors.log`: errores con archivo, línea y traceback completo.
- `logs/audit.log`: ban, unban y broadcasts administrativos.

La consola usa un formato compacto con hora, nivel, componente y mensaje. Pyrogram, aiohttp y asyncio solo muestran errores; yt-dlp conserva también sus warnings técnicos porque suelen requerir atención. Las consultas completas del usuario no se guardan en los logs operativos.

## Estructura

```text
frontend/              interfaz administrativa AllMusic
handlers/              comandos, callbacks y administración Telegram
services/              búsqueda, descarga, enlaces y supervisor yt-dlp
database/              persistencia SQLite
core/                  configuración y logging
tests/                 pruebas automatizadas
bot.py                 composición y ciclo de vida
dashboard.py           API y servidor web
ingestor.py            herramienta privada bajo demanda
main.py                punto de entrada oficial
```
