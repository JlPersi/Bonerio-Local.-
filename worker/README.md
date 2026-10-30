# Bonerío en vivo (Cloudflare Worker)

Un servidor chico entre la página y Primary (cuenta de Bull). Guarda el usuario y la contraseña como *secrets* y le pasa a la página solo los precios.

- `/live/arg_bonds`, `/live/arg_notes`, `/live/arg_corp`, `/live/arg_stocks`, `/live/arg_cedears`: la misma lista y el mismo formato que data912, con precio y puntas de Primary en tiempo real (si Primary falla, devuelve la de data912).
- `/caucion`: la caución de BYMA por plazo, en pesos, MEP y cable.

## Cómo subirlo (una sola vez)

1. Crear una cuenta gratis en https://dash.cloudflare.com (si no tenés).
2. En una terminal, dentro de esta carpeta `worker/`:
   ```
   npx wrangler login
   npx wrangler secret put ROFEX_USER     (pega el usuario de Bull)
   npx wrangler secret put ROFEX_PASS     (pega la contraseña)
   npx wrangler deploy
   ```
3. `deploy` muestra la dirección, algo como `https://bonerio-vivo.TU-USUARIO.workers.dev`.
   Esa dirección va en `window.BL_LIVE = '...'` al principio de `index.html` (o pasásela a Claude).

Para probarlo: abrir `https://bonerio-vivo.TU-USUARIO.workers.dev/live/arg_bonds` en el navegador. Las filas que trae de Primary tienen `"src":"primary"`.

Notas:
- El plan gratis de Workers alcanza para uso personal; si hay muchos visitantes conviene el de 5 USD (más tiempo de CPU por pedido).
- Cada respuesta se guarda 15 segundos, así muchos visitantes a la vez generan una sola consulta a Primary.
- Revisá los términos de uso de Primary/Bull antes de mostrar estos precios a terceros.

## Publicación automática (recomendado)

Desde que el Worker usa la conexión permanente con Primary (Durable Object `Feed`), se publica solo desde GitHub con `.github/workflows/worker.yml` cada vez que cambia algo en `worker/`.

1. En Cloudflare: **My Profile › API Tokens › Create Token** y elegí la plantilla **Edit Cloudflare Workers**. Copiá el token.
2. En GitHub: **Settings › Secrets and variables › Actions › New repository secret**. Nombre: `CLOUDFLARE_API_TOKEN`; valor: el token.
3. En **Actions › Worker en vivo › Run workflow**, publicalo la primera vez.

El usuario y la clave de Bull (`ROFEX_USER`, `ROFEX_PASS`) siguen en el panel de Cloudflare: la publicación no los toca.
