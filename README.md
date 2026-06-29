# depto-bot 🏠

Bot que scrapea portales de alquiler en Córdoba, filtra por tus requisitos y te
manda un reporte por **Telegram cada hora (6–22h)**. Corre gratis en **GitHub
Actions** (sin servidor propio).

## Cómo funciona

```
GitHub Actions (cron, cada hora 6–22h AR)
  main.py
    ├─ scrapers/   un módulo por portal (hoy: La Voz)
    ├─ matcher.py  filtra por precio, zona, ambientes, dormitorios, m2, palabras
    ├─ store.py    deduplica: recuerda qué avisos ya te mandó (state/state.json)
    └─ notifier.py arma y envía el reporte a Telegram
```

- **Si hay deptos nuevos** → te manda la lista de los nuevos.
- **Si no hay nuevos** → igual te escribe (*"No encontramos ningún departamento
  nuevo 🙃"*) y **vuelve a listar los que matchean ahora**.

## Estado de las fuentes

| Fuente | Estado | Nota |
|---|---|---|
| La Voz clasificados | ✅ implementada | API interna vía `curl_cffi` (imita TLS de Chrome) |
| Argenprop | ✅ implementada | HTML vía `curl_cffi`; datos estructurados en atributos |
| Zonaprop | ⏳ pendiente | Cloudflare, difícil |
| MercadoLibre | ❌ descartada | DataDome bloquea el scraping; su API exige OAuth |
| Facebook Marketplace | ⏳ opcional | requiere login, frágil, viola ToS |

> **Argenprop:** se busca por barrio (`slugs` en config) y la zona real de cada
> aviso se deriva del href (las búsquedas mezclan barrios destacados). Güemes no
> tiene slug propio en Argenprop, pero La Voz ya cubre esa zona.
> Al **agregar una fuente nueva**, sus avisos se "siembran" en silencio la primera
> vez (no inunda); desde la corrida siguiente notifica solo los nuevos.

> **Cómo se scrapea La Voz:** su WAF bloquea Playwright y peticiones HTTP comunes
> (403 "Acceso denegado"). Usamos `curl_cffi` con `impersonate="chrome"`, que
> replica el fingerprint TLS de Chrome, y consumimos su API interna
> `/api/search` (subcategoría departamentos + operación alquiler + barrios).

## Configuración

Editá `config.yaml` (filtros y fuentes). No toca código.

## Setup (una sola vez)

### 1. Crear el bot de Telegram
1. En Telegram, hablale a **@BotFather** → `/newbot` → te da un **token**.
2. Escribile algo a tu bot (para iniciar la conversación).
3. Conseguí tu **chat id**: abrí
   `https://api.telegram.org/bot<TOKEN>/getUpdates` en el navegador y buscá
   `"chat":{"id":...}`.

### 2. Subir a GitHub
```bash
cd depto-bot
git init && git add . && git commit -m "init depto-bot"
gh repo create depto-bot --public --source=. --push
```
> Hacé el repo **público** para tener minutos de Actions **ilimitados y gratis**.
> Los secretos NO están en el código, así que es seguro.

### 3. Cargar los secretos
En el repo: **Settings → Secrets and variables → Actions → New secret**:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID` — uno o varios chat ids separados por coma, ej:
  `627176341,987654321` (le manda a todos)

### 4. Probar
Pestaña **Actions → depto-bot → Run workflow** (dispara una corrida manual).

## Probar local (opcional)

```bash
./run_local.sh                 # crea el venv la 1ª vez y corre el bot
# Sin TELEGRAM_BOT_TOKEN/CHAT_ID, imprime el reporte por consola.
```

## Bot interactivo (Render)

El bot ([bot_server.py](bot_server.py)) deja configurar la alarma por Telegram:
`/configurar` (wizard), `/estado`, `/precio`, `/dormitorios`, `/zonas`. Escribe los
filtros en `state/overrides.json` (vía GitHub API) y el scraper los toma en la
próxima corrida. Corre en Render (free) con webhook; un cron de GitHub
([keepalive.yml](.github/workflows/keepalive.yml)) lo pinguea para que no duerma.

### Deploy en Render
1. **PAT de GitHub:** crear un token *fine-grained* con permiso *Contents: Read and
   write* sobre el repo. Será `GITHUB_TOKEN`.
2. En Render: **New + → Blueprint →** conectar este repo (usa `render.yaml`).
3. Cargar las env vars del servicio:
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (ids separados por coma),
   - `WEBHOOK_SECRET` (inventá un string), `GITHUB_TOKEN`, `GITHUB_REPO=torreseze/depto-bot`.
4. Cuando Render te dé la URL (ej. `https://depto-bot.onrender.com`):
   - Registrar el webhook de Telegram:
     `https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://depto-bot.onrender.com/webhook/<WEBHOOK_SECRET>`
   - Agregar el secret `RENDER_URL` en GitHub (Actions) con esa URL, para el keepalive.

## Notas / pendientes

- El cron de GitHub no es exacto al minuto (puede demorarse en horas pico). Para
  "cada hora" no es problema.
- **Riesgo a validar en CI:** el WAF de La Voz podría bloquear la IP de datacenter
  de GitHub Actions aunque `curl_cffi` pase el fingerprint TLS. Se confirma con la
  primera corrida manual (Actions → Run workflow). Si diera 403, la solución es
  usar un proxy residencial.
- Filtro **equilibrado**: excluye monoambientes y exige los requisitos que el
  aviso informa; si no informa m²/dormitorios, lo deja pasar (`strict_unknown:
  false`). Para filtrar fino habría que visitar el detalle de cada aviso (fase 2).
- La primera corrida no inunda: resume el inventario actual, manda algunos
  ejemplos y "marca como vistos" los avisos; desde ahí solo notifica los nuevos.
```
