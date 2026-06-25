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
| La Voz clasificados | ✅ implementada | navegador real (Playwright) |
| Argenprop | ⏳ pendiente | fase 2 |
| Zonaprop | ⏳ pendiente | Cloudflare, difícil |
| MercadoLibre | ❌ descartada | la API ahora exige OAuth |
| Facebook Marketplace | ⏳ opcional | requiere login, frágil, viola ToS |

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
- `TELEGRAM_CHAT_ID`

### 4. Probar
Pestaña **Actions → depto-bot → Run workflow** (dispara una corrida manual).

## Probar local (opcional)

```bash
pip install -r requirements.txt
python -m playwright install chromium
export TELEGRAM_BOT_TOKEN=...   # opcional: sin esto imprime por consola
export TELEGRAM_CHAT_ID=...
python main.py
```

## Notas / pendientes

- El cron de GitHub no es exacto al minuto (puede demorarse en horas pico). Para
  "cada hora" no es problema.
- Los avisos de La Voz a veces no muestran m2/dormitorios en el listado: con
  `strict_unknown: false` (default) esos pasan igual. Para filtrar fino habría
  que visitar la página de detalle de cada aviso (mejora de fase 2).
- La paginación de La Voz usa `?pagina=N` (a confirmar en vivo; ajustar en
  `scrapers/lavoz.py` si hiciera falta).
```
