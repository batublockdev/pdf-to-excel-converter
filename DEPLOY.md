# PDF to Excel Converter

Convierte estados de cuenta PDF a Excel limpio automáticamente.

## Inicio Rápido

### Backend (Python + FastAPI)

```bash
cd backend

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Correr servidor
uvicorn main:app --reload --port 8000
```

### Frontend (Next.js)

```bash
cd frontend

# Instalar dependencias
npm install

# Configurar API URL
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Correr servidor
npm run dev
```

Abrir http://localhost:3000

## Deploy

### Backend en Railway

1. Crear cuenta en [railway.app](https://railway.app)
2. New Project → Deploy from GitHub repo
3. Configurar:
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Environment: `GEMINI_API_KEY=tu_key` (opcional)

### Frontend en Vercel

1. Crear cuenta en [vercel.com](https://vercel.com)
2. Import Project → Seleccionar repo
3. Configurar:
   - Framework: Next.js
   - Environment: `NEXT_PUBLIC_API_URL=https://tu-backend.railway.app`

## Estructura

```
pdf-converters/
├── backend/           # FastAPI + Python
│   ├── main.py       # API principal
│   ├── requirements.txt
│   └── README.md
│
├── frontend/         # Next.js + React
│   ├── pages/
│   │   └── index.tsx
│   ├── styles/
│   │   └── globals.css
│   ├── package.json
│   └── README.md
│
├── PLAN.md          # Plan del proyecto
└── README.md        # Este archivo
```

## API Endpoints

### `POST /api/convert`
Convierte un PDF a Excel.

### `POST /api/convert/bulk`
Convierte múltiples PDFs a un Excel consolidado.

### `POST /api/preview`
Vista previa del PDF (primeras 10 filas).

### `GET /health`
Health check del servidor.

## Costos

### Free Tier
- Railway: $5/mes credit (gratis para MVP)
- Vercel: Gratis para proyectos pequeños
- Gemini API: 15 req/min gratis

### Con Usuarios
- Railway: ~$5-10/mes
- Vercel Pro: $20/mes (opcional)
- Gemini API: $0.01 por request extra

## Roadmap

### Fase 1 (Actual)
- [x] Backend MVP
- [x] Frontend básico
- [ ] Deploy
- [ ] Testing con PDFs reales

### Fase 2 (30 días)
- [ ] Bulk upload
- [ ] Detección inteligente de bancos
- [ ] Multi-idioma mejorado
- [ ] Email collection

### Fase 3 (60 días)
- [ ] Stripe integration
- [ ] Plan gratuito (3 PDFs)
- [ ] Plan pago ($9/mes)
- [ ] SEO programático

## Licencia

MIT