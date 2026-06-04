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
import re
from typing import List

# Configuración
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDF to Excel Converter",
    description="Convierte estados de cuenta PDF a Excel limpio",
    version="1.0.6"
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
    """Convierte índice a letra de columna de Excel"""
    result = ""
    idx += 1
    while idx > 0:
        idx -= 1
        result = chr(65 + idx % 26) + result
        idx //= 26
    return result


def extract_tables_pdfplumber(pdf_path: str) -> List:
    """Extrae tablas usando pdfplumber con múltiples estrategias"""
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            try:
                # Estrategia 1: Tablas con líneas
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        # Filtrar tablas muy pequeñas
                        if len(table) >= 2:
                            all_tables.append({
                                "page": page_num + 1,
                                "data": table,
                                "type": "lined"
                            })

                # Estrategia 2: Texto con patrones de factura
                text = page.extract_text()
                if text and (not tables or len(tables) == 0):
                    # Detectar si es factura con patrones
                    if any(kw in text for kw in ['Total', 'Consumo', 'Valor', '$', 'factura', 'periodo']):
                        lines = text.split('\n')
                        table_data = []
                        for line in lines:
                            if line.strip():
                                # Separar por espacios múltiples o tabs
                                parts = re.split(r'\s{2,}|\t', line.strip())
                                if len(parts) >= 2:
                                    table_data.append(parts)
                        
                        if len(table_data) >= 2:
                            all_tables.append({
                                "page": page_num + 1,
                                "data": table_data,
                                "type": "text-invoice"
                            })

            except Exception as e:
                logger.warning(f"Error en página {page_num}: {e}")
                continue

    return all_tables


def clean_and_organize_invoice(tables: List) -> pd.DataFrame:
    """Organiza datos de factura en formato limpio"""
    all_records = []
    
    for table_info in tables:
        table = table_info["data"]
        
        for row in table:
            if not row or not any(cell for cell in row if cell):
                continue
            
            # Limpiar celdas
            clean_row = []
            for cell in row:
                if cell:
                    cell = str(cell).strip()
                    # Limpiar caracteres extraños
                    cell = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cell)
                    clean_row.append(cell)
            
            if clean_row:
                all_records.append(clean_row)
    
    if not all_records:
        return pd.DataFrame()
    
    # Encontrar el número máximo de columnas
    max_cols = max(len(row) for row in all_records)
    
    # Normalizar todas las filas al mismo número de columnas
    normalized_rows = []
    for row in all_records:
        if len(row) < max_cols:
            row = list(row) + [''] * (max_cols - len(row))
        else:
            row = row[:max_cols]
        normalized_rows.append(row)
    
    # Crear DataFrame
    df = pd.DataFrame(normalized_rows)
    
    # Intentar detectar headers en la primera fila
    if len(df) > 0:
        # Usar la primera fila como header si parece serlo
        first_row = df.iloc[0].tolist()
        if any(isinstance(cell, str) and any(kw in cell.lower() for kw in ['total', 'valor', 'consumo', 'fecha', 'descripcion', 'concepto']) for cell in first_row):
            df.columns = first_row
            df = df.iloc[1:]
        else:
            # Crear headers genéricos
            df.columns = [f"Columna_{i+1}" for i in range(len(df.columns))]
    
    # Limpiar filas vacías
    df = df.dropna(how='all')
    df = df.reset_index(drop=True)
    
    return df


def detect_bank_statement(df: pd.DataFrame) -> bool:
    """Detecta si el PDF es un estado de cuenta bancario"""
    keywords = [
        "balance", "saldo", "crédito", "débito", "credit", "debit",
        "deposit", "retiro", "transferencia", "fecha", "date"
    ]

    text = " ".join(str(col).lower() for col in df.columns)
    matches = sum(1 for kw in keywords if kw in text)
    return matches >= 3


@app.get("/")
async def root():
    return {
        "message": "PDF to Excel Converter API",
        "version": "1.0.6",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/convert")
async def convert_pdf(file: UploadFile = File(...)):
    """Convierte un PDF a Excel"""
    logger.info(f"Recibiendo archivo: {file.filename}")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    try:
        content = await file.read()
        logger.info(f"Archivo recibido: {len(content)} bytes")

        if len(content) == 0:
            raise HTTPException(status_code=400, detail="El archivo está vacío")

        if not content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="El archivo no es un PDF válido")

    except Exception as e:
        logger.error(f"Error leyendo archivo: {e}")
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {str(e)}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        logger.info(f"Procesando: {file.filename}")

        tables = extract_tables_pdfplumber(tmp_path)
        logger.info(f"Tablas encontradas: {len(tables)}")
        
        if not tables:
            raise HTTPException(status_code=400, detail="No se encontraron tablas en el PDF")

        df = clean_and_organize_invoice(tables)

        if df.empty:
            raise HTTPException(status_code=400, detail="No se pudieron extraer datos válidos")

        logger.info(f"Convertido: {len(df)} filas, {len(df.columns)} columnas")

        # Crear Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Datos')
            
            # Formatear
            worksheet = writer.sheets['Datos']
            
            # Auto-ajustar columnas
            for idx, col in enumerate(df.columns):
                col_letter = get_column_letter(idx)
                try:
                    max_length = max(
                        df[col].astype(str).map(len).max(),
                        len(str(col))
                    )
                    worksheet.column_dimensions[col_letter].width = min(max_length + 2, 50)
                except:
                    worksheet.column_dimensions[col_letter].width = 15
            
            # Agregar filtros
            worksheet.auto_filter.ref = worksheet.dimensions

        output.seek(0)
        excel_filename = file.filename.replace('.pdf', '.xlsx')

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{excel_filename}"'}
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
    """Vista previa del PDF"""
    logger.info(f"Preview: {file.filename}")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    try:
        content = await file.read()
        if len(content) == 0 or not content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="PDF inválido")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        tables = extract_tables_pdfplumber(tmp_path)
        
        if not tables:
            return {
                "filename": file.filename,
                "total_rows": 0,
                "is_bank_statement": False,
                "columns": [],
                "preview": []
            }

        df = clean_and_organize_invoice(tables)
        preview = df.head(10).to_dict(orient='records')

        return {
            "filename": file.filename,
            "total_rows": len(df),
            "is_bank_statement": detect_bank_statement(df),
            "columns": list(df.columns),
            "preview": preview
        }

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)