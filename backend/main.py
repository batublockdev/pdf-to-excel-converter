"""
PDF to Excel Converter - Backend
Convierte PDFs (estados de cuenta, facturas, tablas) a Excel limpio
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import pdfplumber
import pandas as pd
from io import BytesIO
import tempfile
import os
import logging
from typing import List, Optional
import google.generativeai as genai

# Configuración
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDF to Excel Converter",
    description="Convierte estados de cuenta PDF a Excel limpio",
    version="1.0.0"
)

# CORS para frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción: dominio específico
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar Gemini (opcional, para parsing inteligente)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def extract_tables_pdfplumber(pdf_path: str) -> List[List]:
    """Extrae tablas usando pdfplumber (más robusto para estados de cuenta)"""
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            try:
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        # Agregar número de página para referencia
                        all_tables.append({
                            "page": page_num + 1,
                            "data": table
                        })
            except Exception as e:
                logger.warning(f"Error en página {page_num}: {e}")
                continue

    return all_tables


def clean_table_data(tables: List[dict]) -> pd.DataFrame:
    """Limpia y consolida las tablas extraídas"""
    all_rows = []

    for table_info in tables:
        table = table_info["data"]
        if len(table) > 1:
            # Primera fila como headers
            headers = table[0]
            for row in table[1:]:
                if row and any(cell for cell in row if cell):  # Filtrar filas vacías
                    all_rows.append(row)

    if not all_rows:
        return pd.DataFrame()

    # Crear DataFrame
    df = pd.DataFrame(all_rows)

    # Limpiar nombres de columnas
    if len(tables) > 0 and len(tables[0]["data"]) > 0:
        df.columns = tables[0]["data"][0]

    return df


def detect_bank_statement(df: pd.DataFrame) -> bool:
    """Detecta si el PDF es un estado de cuenta bancario"""
    keywords = [
        "balance", "saldo", "balance", "crédito", "débito",
        "deposit", "retiro", "transferencia", "fecha", "date",
        "descripcion", "description", "referencia", "reference"
    ]

    text = " ".join(str(col).lower() for col in df.columns)

    # También buscar en primeras filas
    if len(df) > 0:
        for row in df.head(3).values:
            text += " ".join(str(cell).lower() for cell in row if cell)

    matches = sum(1 for kw in keywords if kw in text)
    return matches >= 3


def parse_with_gemini(df: pd.DataFrame, pdf_path: str) -> pd.DataFrame:
    """Usa Gemini para parsear mejor los datos (opcional)"""
    if not GEMINI_API_KEY:
        return df

    try:
        # Extraer texto del PDF para contexto
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages[:2]:  # Solo primeras 2 páginas
                text += page.extract_text() or ""

        # Prompt para Gemini
        prompt = f"""
        Analiza este estado de cuenta bancario y extrae las transacciones principales.
        Formato del texto: {text[:2000]}

        Devuelve un JSON con las columnas correctas:
        - Fecha
        - Descripción
        - Débito/Crédito o Monto
        - Saldo/Balance

        Si no es un estado de cuenta, devuelve la tabla original.
        """

        model = genai.GenerativeModel('gemini-flash')
        response = model.generate_content(prompt)

        # Parsear respuesta de Gemini
        # Por ahora, retornar el DataFrame original
        return df

    except Exception as e:
        logger.warning(f"Error con Gemini: {e}")
        return df


@app.get("/")
async def root():
    return {
        "message": "PDF to Excel Converter API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/convert")
async def convert_pdf(file: UploadFile = File(...)):
    """
    Convierte un PDF a Excel
    - Acepta PDFs con tablas
    - Detecta automáticamente si es estado de cuenta
    - Devuelve Excel limpio
    """
    # Validar tipo de archivo
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    # Guardar temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        logger.info(f"Procesando: {file.filename}")

        # Extraer tablas
        tables = extract_tables_pdfplumber(tmp_path)

        if not tables:
            raise HTTPException(status_code=400, detail="No se encontraron tablas en el PDF")

        # Limpiar y consolidar
        df = clean_table_data(tables)

        if df.empty:
            raise HTTPException(status_code=400, detail="No se pudieron extraer datos válidos")

        # Detectar si es estado de cuenta
        is_bank_statement = detect_bank_statement(df)
        logger.info(f"Es estado de cuenta: {is_bank_statement}")

        # Si es estado de cuenta y tenemos Gemini, intentar parseo inteligente
        if is_bank_statement and GEMINI_API_KEY:
            df = parse_with_gemini(df, tmp_path)

        # Crear Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Datos')

            # Auto-ajustar columnas
            worksheet = writer.sheets['Datos']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).map(len).max(),
                    len(str(col))
                )
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)

        output.seek(0)

        # Generar nombre de archivo
        excel_filename = file.filename.replace('.pdf', '.xlsx')

        logger.info(f"Convertido: {len(df)} filas")

        # Devolver como descarga
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{excel_filename}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando PDF: {str(e)}")
    finally:
        # Siempre borrar el archivo temporal
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/api/convert/bulk")
async def convert_bulk_pdfs(files: List[UploadFile] = File(...)):
    """
    Convierte múltiples PDFs a un solo Excel consolidado
    - Máximo 50 archivos
    - Consolidado en un solo archivo
    """
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Máximo 50 archivos permitidos")

    all_data = []

    for file in files:
        # Guardar temporalmente
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Extraer y limpiar
            tables = extract_tables_pdfplumber(tmp_path)
            df = clean_table_data(tables)

            # Agregar columna de origen
            df['archivo_origen'] = file.filename

            all_data.append(df)

        except Exception as e:
            logger.warning(f"Error en {file.filename}: {e}")
            continue
        finally:
            os.unlink(tmp_path)

    if not all_data:
        raise HTTPException(status_code=400, detail="No se pudieron procesar archivos")

    # Consolidar
    consolidated = pd.concat(all_data, ignore_index=True)

    # Crear Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        consolidated.to_excel(writer, index=False, sheet_name='Consolidado')

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="consolidado.xlsx"'
        }
    )


@app.post("/api/preview")
async def preview_pdf(file: UploadFile = File(...)):
    """
    Vista previa del PDF sin descargar
    - Devuelve las primeras 10 filas
    - Útil para validar antes de convertir
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        tables = extract_tables_pdfplumber(tmp_path)
        df = clean_table_data(tables)

        # Primeras 10 filas
        preview = df.head(10).to_dict(orient='records')

        return {
            "filename": file.filename,
            "total_rows": len(df),
            "is_bank_statement": detect_bank_statement(df),
            "columns": list(df.columns),
            "preview": preview
        }

    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)