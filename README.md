# Lo que tengo, lo que como

App web full stack que arma menús equilibrados con los alimentos que la persona tiene en casa, con tienda de utensilios, contacto, panel de administrador y asistente con IA.

## Estructura
- `frontend/` — páginas estáticas (HTML, CSS, JavaScript y React para el login). Se publican en **GitHub Pages**.
  `index` (marca y home) · `catalogo` · `contacto` · `auth` (login/registro/verificación, React) · `app` (nevera, menú, progreso, asistente) · `admin`
- `backend/` — API en Python (FastAPI + pandas + MongoDB). Se publica en **Render**.
  `main.py` (rutas) · `nucleo.py` (lógica de menús) · `alimentos.csv` (base de alimentos) · `datos_iniciales.py` (catálogo de ejemplo)

## Probar en tu computador
```
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload
```
Abre http://localhost:8000 (el backend sirve el frontend solo en pruebas locales).

## Publicar
1. **Backend en Render:** New → Web Service → tu repositorio. Root Directory: `backend`. Build: `pip install -r requirements.txt`. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
   Variables de entorno: `MONGO_URI` (obligatoria para que los datos no se pierdan), `JWT_SECRET`, `ADMIN_USER`, `ADMIN_CLAVE`, `ORIGENES` (la dirección de tu GitHub Pages), `ANTHROPIC_API_KEY` (para la IA; opcional) y `SMTP_HOST`, `SMTP_USER`, `SMTP_CLAVE` (correos de verificación; opcionales).
2. **Frontend:** en `frontend/config.js` cambia `TU-BACKEND` por el nombre de tu servicio de Render.
3. **GitHub Pages:** Settings → Pages → Source: **GitHub Actions**. Cada push a `main` publica la carpeta `frontend`.

## Fotos de productos
Guarda las fotos en `frontend/img/` y en el panel de administrador escribe su ruta (ej.: `img/balanza.jpg`). Sin foto se muestra un emoji.
