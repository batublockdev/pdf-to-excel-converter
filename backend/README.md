# PDF to Excel Converter API

Backend para convertir PDFs a Excel.

## Instalación

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt
```

## Uso

```bash
# Desarrollo
uvicorn main:app --reload --port 8000

# Producción
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Endpoints

### `POST /api/convert`
Convierte un PDF a Excel.

**Request:**
- `file`: archivo PDF

**Response:**
- Archivo Excel (.xlsx)

### `POST /api/convert/bulk`
Convierte múltiples PDFs a un Excel consolidado.

**Request:**
- `files`: lista de PDFs (máx 50)

**Response:**
- Archivo Excel consolidado (.xlsx)

### `POST /api/preview`
Vista previa del PDF (primeras 10 filas).

**Response:**
```json
{
  "filename": "documento.pdf",
  "total_rows": 150,
  "is_bank_statement": true,
  "columns": ["Fecha", "Descripción", "Monto"],
  "preview": [...]
}
```

## Deploy en Railway

1. Crear cuenta en railway.app
2. Conectar repositorio
3. Configurar:
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Environment variables: `GEMINI_API_KEY` (opcional)

## Costos

- Railway free tier: $5/mes credit
- Gemini API free tier: 15 req/min
- Sin base de datos: procesamiento en memoria