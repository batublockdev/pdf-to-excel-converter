# Proyecto: PDF Converters SaaS

## Productos
1. **Bank Statement Converter** - Convierte estados de cuenta PDF a Excel limpio
2. **PDF to Excel Converter** - Convierte cualquier PDF tabular a Excel

## Estado
- [x] Investigación completada
- [x] Plan definido
- [ ] MVP desarrollo (EN PROGRESO)
- [ ] Deploy
- [ ] Landing page
- [ ] Promoción

## Fecha inicio: 2026-06-04
## Meta: $1,250/mes en 60 días

---

## Stack Técnico (FREE tier primero)

### Backend
- **Python** + FastAPI
- **pdfplumber** (gratis, open source) para extracción básica
- **Camelot** (gratis, open source) para tablas complejas
- **Gemini Flash API** (gratis tier: 15 req/min) para parsing inteligente
- **Railway** (gratis tier: $5 credit/mes) para deploy

### Frontend
- **Next.js** + React + TypeScript
- **Tailwind CSS** para UI
- **Vercel** (gratis) para hosting

### Storage
- **Local temp** - procesar en memoria, borrar inmediatamente
- **Sin base de datos** por ahora (MVP)

### Pagos
- **Stripe** (crear cuenta cuando tengamos usuarios)
- Por ahora: **gratis** para validar

---

## Plan de Desarrollo

### Fase 1: MVP (7 días) - GRATIS
- [Día 1-2] Backend Python básico
  - Upload PDF
  - Extracción con pdfplumber
  - Output Excel limpio
  - API REST simple

- [Día 3-4] Frontend básico
  - Página de upload
  - Progreso visual
  - Descarga del resultado

- [Día 5] Landing page
  - Hero + CTA
  - 3 beneficios
  - FAQ básico
  - SEO mínimo

- [Día 6-7] Deploy + testing
  - Railway para backend
  - Vercel para frontend
  - Testing con PDFs reales

### Fase 2: Validación (30 días)
- [ ] Lanzar gratis
- [ ] Medir conversión (upload → download)
- [ ] Recolectar emails
- [ ] Pedir feedback
- [ ] Arreglar bugs

### Fase 3: Monetización (60 días)
- [ ] Activar Stripe
- [ ] Plan gratuito (3 PDFs)
- [ ] Plan pago ($9/mes)
- [ ] Outreach agresivo

---

## Costos Fase 1 (FREE)

| Servicio | Costo |
|----------|-------|
| Dominio | $12/año (único gasto) |
| Vercel | $0 (free tier) |
| Railway | $0 (free tier) |
| Gemini API | $0 (free tier: 15 req/min) |
| Stripe | $0 (solo se activa con pagos) |
| **Total** | **$12 total** |

---

## Costos Fase 2 (con usuarios)

| Servicio | Costo/mes |
|----------|-----------|
| Vercel Pro | $20 (opcional) |
| Railway | $5 (si excede free) |
| Gemini API | $0-10 (depende uso) |
| Stripe fees | 2.9% de ingresos |
| **Total** | **$5-30/mes** |

---

## Código Base

### Backend (FastAPI)

```python
# main.py
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import pandas as pd
from io import BytesIO
import tempfile
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/convert")
async def convert_pdf(file: UploadFile = File(...)):
    # Guardar temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Extraer tablas
        tables = []
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                tables.extend(page_tables)

        # Convertir a DataFrame
        all_rows = []
        for table in tables:
            all_rows.extend(table)

        df = pd.DataFrame(all_rows[1:], columns=all_rows[0] if all_rows else None)

        # Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)

        return {"status": "success", "rows": len(df)}

    finally:
        os.unlink(tmp_path)
```

### Frontend (Next.js mínimo)

```tsx
// pages/index.tsx
import { useState } from 'react'
import { Upload, Button, message } from 'antd'

export default function Home() {
  const [loading, setLoading] = useState(false)

  const handleUpload = async (file: File) => {
    setLoading(true)
    const formData = new FormData()
    formData.append('file', file)

    const res = await fetch('/api/convert', {
      method: 'POST',
      body: formData
    })

    const data = await res.json()
    setLoading(false)

    if (data.status === 'success') {
      message.success(`Convertido: ${data.rows} filas`)
      // Descargar Excel...
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <div className="max-w-4xl mx-auto px-4 py-16">
        <h1 className="text-4xl font-bold text-center mb-4">
          Convierte PDF a Excel en Segundos
        </h1>
        <p className="text-xl text-gray-600 text-center mb-8">
          Estados de cuenta, facturas, tablas - todo a Excel limpio
        </p>

        <Upload.Dragger
          accept=".pdf"
          beforeUpload={(file) => {
            handleUpload(file)
            return false
          }}
          showUploadList={false}
        >
          <p className="text-lg">Arrastra tu PDF aquí</p>
        </Upload.Dragger>

        {loading && <p className="text-center mt-4">Procesando...</p>}
      </div>
    </div>
  )
}
```

---

## Próximos Pasos HOY

1. [ ] Crear cuenta Stripe (Batu lo hace)
2. [ ] Comprar dominio ($12) - opciones:
   - pdfaexcel.com
   - convertirpdf.co
   - bancoexcel.com
3. [ ] Yo escribo código backend (ahora)
4. [ ] Yo creo frontend básico (mañana)
5. [ ] Deploy a Railway + Vercel (viernes)

---

## Validación GRATIS primero

### Estrategia:
1. **Semana 1-2:** Producto GRATIS
   - Sin límite de uso
   - Recolectamos emails
   - Medimos conversión real

2. **Semana 3-4:** Activamos Stripe
   - Plan gratis: 3 PDFs
   - Plan pago: $9/mes ilimitado
   - Email a usuarios existentes con oferta

3. **Semana 5-8:** Outreach
   - LinkedIn contadores
   - Facebook grupos
   - SEO orgánico

### Métricas de éxito (fase gratuita):
- 100 uploads en 2 semanas = validado
- 50 emails recolectados = hay interés
- 10 usuarios repiten = producto útil

---

## Diferenciadores (para cuando cobremos)

1. **Multi-idioma:** Español + Portugués + Francés (mercado latino)
2. **Bulk upload:** 50 PDFs → 1 Excel
3. **Mobile-first:** Funciona en celular
4. **Privacy:** Zero retention, borramos todo

---

*Última actualización: 2026-06-04*