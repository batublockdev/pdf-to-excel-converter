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
from typing import List

# Configuración
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDF to Excel Converter",
    description="Convierte estados de cuenta PDF a Excel limpio",
    version="1.0.3"
)

# CORS para frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_column_letter(idx: int) -> str:
    """Convierte índice a letra de columna de Excel (A, B, ..., Z, AA, AB, ...)"""
    result = ""
    idx += 1  # Convertir a 1-indexed
    while idx > 0:
        idx -= 1
        result = chr(65 + idx % 26) + result
        idx //= 26
    return result


def extract_tables_pdfplumber(pdf_path: str) -> List:
    """Extrae tablas usando pdfplumber"""
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            try:
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        all_tables.append({
                            "page": page_num + 1,
                            "data": table
                        })
            except Exception as e:
                logger.warning(f"Error en página {page_num}: {e}")
                continue

    return all_tables


def clean_table_data(tables: List) -> pd.DataFrame:
    """Limpia y consolida las tablas extraídas"""
    all_rows = []
    max_columns = 0
    header = None

    for table_info in tables:
        table = table_info["data"]
        if len(table) > 1:
            # Usar la primera fila como header
            if header is None and len(table[0]) > max_columns:
                header = table[0]
                max_columns = len(table[0])
            
            for row in table[1:]:
                if row and any(cell for cell in row if cell):
                    # Normalizar longitud de filas
                    if len(row) < max_columns:
                        row = list(row) + [None] * (max_columns - len(row))
                    elif len(row) > max_columns:
                        row = row[:max_columns]
                    all_rows.append(row)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    if header and len(header) > 0:
        # Asegurar que el header tenga la misma longitud
        if len(header) < len(df.columns):
            header = list(header) + [f"Columna_{i}" for i in range(len(header), len(df.columns))]
        elif len(header) > len(df.columns):
            header = header[:len(df.columns)]
        df.columns = header

    return df


def detect_bank_statement(df: pd.DataFrame) -> bool:
    """Detecta si el PDF es un estado de cuenta bancario"""
    keywords = [
        "balance", "saldo", "crédito", "débito", "credit", "debit",
        "deposit", "retiro", "transferencia", "fecha", "date",
        "descripcion", "description", "referencia", "reference"
    ]

    text = " ".join(str(col).lower() for col in df.columns)
    if len(df) > 0:
        for row in df.head(3).values:
            text += " ".join(str(cell).lower() for cell in row if cell)

    matches = sum(1 for kw in keywords if kw in text)
    return matches >= 3


@app.get("/")
async def root():
    return {
        "message": "PDF to Excel Converter API",
        "version": "1.0.3",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/convert")
async def convert_pdf(file: UploadFile = File(...)):
    """Convierte un PDF a Excel"""
    logger.info(f"Recibiendo archivo: {file.filename}, content_type: {file.content_type}")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    # Leer contenido
    try:
        content = await file.read()
        logger.info(f"Archivo recibido: {len(content)} bytes")

        if len(content) == 0:
            raise HTTPException(status_code=400, detail="El archivo está vacío")

        # Verificar que sea un PDF válido (magic bytes)
        if not content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="El archivo no es un PDF válido")

    except Exception as e:
        logger.error(f"Error leyendo archivo: {e}")
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {str(e)}")

    # Guardar temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        logger.info(f"Procesando: {file.filename}")

        # Extraer tablas
        try:
            tables = extract_tables_pdfplumber(tmp_path)
        except Exception as e:
            logger.error(f"Error extrayendo tablas: {e}")
            raise HTTPException(status_code=400, detail=f"Error procesando PDF: {str(e)}")

        if not tables:
            raise HTTPException(status_code=400, detail="No se encontraron tablas en el PDF")

        # Limpiar y consolidar
        df = clean_table_data(tables)

        if df.empty:
            raise HTTPException(status_code=400, detail="No se pudieron extraer datos válidos")

        logger.info(f"Convertido: {len(df)} filas, {len(df.columns)} columnas")

        # Crear Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Datos')

            # Auto-ajustar columnas
            worksheet = writer.sheets['Datos']
            for idx in range(len(df.columns)):
                col_letter = get_column_letter(idx)
                try:
                    max_length = max(
                        df.iloc[:, idx].astype(str).map(len).max(),
                        len(str(df.columns[idx]))
                    )
                    worksheet.column_dimensions[col_letter].width = min(max_length + 2, 50)
                except:
                    worksheet.column_dimensions[col_letter].width = 15

        output.seek(0)

        # Generar nombre de archivo
        excel_filename = file.filename.replace('.pdf', '.xlsx')

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
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/api/preview")
async def preview_pdf(file: UploadFile = File(...)):
    """Vista previa del PDF sin descargar"""
    logger.info(f"Preview - Recibiendo archivo: {file.filename}, content_type: {file.content_type}")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    # Leer contenido
    try:
        content = await file.read()
        logger.info(f"Preview - Archivo recibido: {len(content)} bytes")

        if len(content) == 0:
            raise HTTPException(status_code=400, detail="El archivo está vacío")

        # Verificar que sea un PDF válido (magic bytes)
        if not content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="El archivo no es un PDF válido")

    except Exception as e:
        logger.error(f"Error leyendo archivo: {e}")
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {str(e)}")

    # Guardar temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        try:
            tables = extract_tables_pdfplumber(tmp_path)
        except Exception as e:
            logger.error(f"Error extrayendo tablas: {e}")
            raise HTTPException(status_code=400, detail=f"Error procesando PDF: {str(e)}")

        df = clean_table_data(tables)

        preview = df.head(10).to_dict(orient='records')

        return {
            "filename": file.filename,
            "total_rows": len(df),
            "is_bank_statement": detect_bank_statement(df),
            "columns": list(df.columns),
            "preview": preview
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en preview: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando PDF: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)