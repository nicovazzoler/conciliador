# Timbre

Recibe los webhooks de Mercado Pago, valida la firma y guarda solo de qué se avisó (tipo, acción e id).
No tiene token de Mercado Pago: el detalle de cada aviso lo pide el conciliador desde tu máquina.

| Ruta | Qué hace |
|---|---|
| `GET /` | Responde `{"ok": true}`. Lo usa el healthcheck. |
| `POST /webhook` | La URL que se carga en Mercado Pago. Sin firma válida responde 401. |
| `GET /avisos` | Los últimos 200 avisos. Pide `Authorization: Bearer <TIMBRE_CLAVE>`. |

Los avisos viven en memoria: un redeploy los borra. Los logs de Railway quedan.

## Variables

| Variable | De dónde sale |
|---|---|
| `MP_WEBHOOK_SECRET` | Mercado Pago → Tus integraciones → tu aplicación → Webhooks → clave secreta |
| `TIMBRE_CLAVE` | La inventás vos. Es para leer `/avisos`. |

`PORT` la pone Railway.

## Deploy en Railway

1. New Project → Deploy from GitHub repo → este repo.
2. Settings del servicio:
   - **Root Directory:** `timbre`
   - **Branch:** la que tenga esta carpeta.
   - **Networking → Generate Domain.**
3. Variables: `TIMBRE_CLAVE` y, cuando la tengas, `MP_WEBHOOK_SECRET`.

Arranca solo con `python main.py`. El `railway.json` suma el healthcheck, pero Railway no lo busca
dentro del Root Directory: para usarlo, en Settings → Config-as-code poné `/timbre/railway.json`.

## Probar

En Mercado Pago, cargá `https://<tu-dominio>/webhook` con el evento Pagos y usá "Simular notificación".
En los logs tiene que aparecer `AVISO payment ... real=False`.

```bash
curl https://<tu-dominio>/avisos -H "Authorization: Bearer <TIMBRE_CLAVE>"
```

## Local

```bash
pip install -r requirements.txt
MP_WEBHOOK_SECRET=x TIMBRE_CLAVE=y python main.py
```
