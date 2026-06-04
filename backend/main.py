"""
PDF to Excel Converter - Backend v2.0
Convierte cualquier PDF a Excel extrayendo todo el contenido posible
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDF to Excel Converter",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_column_letter(idx: int) -> str:
    result = ""
    idx += 1
    while idx > 0:
        idx -= 1
        result = chr(65 + idx % 26) + result
        idx //= 26
    return result


def extract_all_text_structured(pdf_path: str) -> pd.DataFrame:
    """Extrae TODO el texto del PDF y lo organiza por líneas"""
    all_lines = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Separar por múltiples espacios (común en PDFs)
                parts = re.split(r'\s{2,}', line)
                
                # Limpiar partes vacías
                parts = [p.strip() for p in parts if p.strip()]
                
                if parts:
                    all_lines.append({
                        'pagina': page_num + 1,
                        'contenido': line,
                        'partes': parts
                    })
    
    if not all_lines:
        return pd.DataFrame()
    
    # Encontrar el máximo número de columnas
    max_parts = max(len(line['partes']) for line in all_lines)
    
    # Crear filas normalizadas
    rows = []
    for line in all_lines:
        row = line['partes']
        if len(row) < max_parts:
            row = list(row) + [''] * (max_parts - len(row))
        rows.append(row[:max_parts])
    
    # Crear DataFrame
    df = pd.DataFrame(rows)
    
    # Crear headers genéricos
    df.columns = [f"Columna_{i+1}" for i in range(len(df.columns))]
    
    return df


def extract_with_words(pdf_path: str) -> pd.DataFrame:
    """Extrae texto usando palabras individuales con posiciones"""
    all_rows = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            words = page.extract_words()
            if not words:
                continue
            
            # Agrupar palabras por línea (posición Y similar)
            lines = {}
            for word in words:
                y = round(word['top'], -1)  # Redondear a 10 pixels
                if y not in lines:
                    lines[y] = []
                lines[y].append(word)
            
            # Ordenar líneas por Y
            for y in sorted(lines.keys()):
                line_words = sorted(lines[y], key=lambda w: w['x0'])
                row = [w['text'] for w in line_words]
                if row:
                    all_rows.append(row)
    
    if not all_rows:
        return pd.DataFrame()
    
    # Normalizar número de columnas
    max_cols = max(len(row) for row in all_rows)
    
    normalized = []
    for row in all_rows:
        if len(row) < max_cols:
            row = list(row) + [''] * (max_cols - len(row))
        normalized.append(row[:max_cols])
    
    df = pd.DataFrame(normalized)
    df.columns = [f"Columna_{i+1}" for i in range(len(df.columns))]
    
    return df


def extract_tables_traditional(pdf_path: str) -> pd.DataFrame:
    """Extrae tablas de la forma tradicional"""
    all_tables = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            try:
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) >= 2:
                        # Limpiar tabla
                        clean_table = []
                        for row in table:
                            clean_row = [str(cell).strip() if cell else '' for cell in row]
                            if any(clean_row):
                                clean_table.append(clean_row)
                        if clean_table:
                            all_tables.extend(clean_table)
            except:
                continue
    
    if not all_tables:
        return pd.DataFrame()
    
    # Normalizar
    max_cols = max(len(row) for row in all_tables)
    
    normalized = []
    for row in all_tables:
        if len(row) < max_cols:
            row = list(row) + [''] * (max_cols - len(row))
        normalized.append(row[:max_cols])
    
    df = pd.DataFrame(normalized)
    df.columns = [f"Columna_{i+1}" for i in range(len(df.columns))]
    
    return df


def smart_extract(pdf_path: str) -> pd.DataFrame:
    """Intenta múltiples métodos de extracción y devuelve el mejor resultado"""
    
    # Método 1: Tablas tradicionales
    df_tables = extract_tables_traditional(pdf_path)
    
    # Método 2: Texto estructurado por espacios
    df_text = extract_all_text_structured(pdf_path)
    
    # Método 3: Palabras con posición
    df_words = extract_with_words(pdf_path)
    
    # Elegir el mejor resultado (más datos)
    results = [
        ('tables', df_tables, len(df_tables) if not df_tables.empty else 0),
        ('text', df_text, len(df_text) if not df_text.empty else 0),
        ('words', df_words, len(df_words) if not df_words.empty else 0)
    ]
    
    # Ordenar por número de filas
    results.sort(key=lambda x: x[2], reverse=True)
    
    logger.info(f"Resultados: tables={results[0][2]} filas, text={results[1][2]} filas, words={results[2][2]} filas")
    
    # Devolver el mejor
    best_method, best_df, _ = results[0]
    
    if best_df.empty:
        return pd.DataFrame()
    
    logger.info(f"Mejor método: {best_method} con {len(best_df)} filas")
    
    return best_df


@app.get("/")
async def root():
    return {"message": "PDF to Excel Converter API", "version": "2.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/convert")
async def convert_pdf(file: UploadFile = File(...)):
    logger.info(f"Recibiendo: {file.filename}")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="El archivo está vacío")
        if not content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="No es un PDF válido")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        df = smart_extract(tmp_path)
        
        if df.empty:
            raise HTTPException(status_code=400, detail="No se pudo extraer contenido del PDF")

        logger.info(f"Convertido: {len(df)} filas, {len(df.columns)} columnas")

        # Crear Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Datos')
            
            # Formatear
            worksheet = writer.sheets['Datos']
            for idx in range(len(df.columns)):
                col_letter = get_column_letter(idx)
                try:
                    max_len = max(
                        df.iloc[:, idx].astype(str).map(len).max(),
                        len(str(df.columns[idx]))
                    )
                    worksheet.column_dimensions[col_letter].width = min(max_len + 2, 60)
                except:
                    worksheet.column_dimensions[col_letter].width = 20
            
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
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/api/preview")
async def preview_pdf(file: UploadFile = File(...)):
    logger.info(f"Preview: {file.filename}")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo PDFs")

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
        df = smart_extract(tmp_path)
        
        if df.empty:
            return {
                "filename": file.filename,
                "total_rows": 0,
                "columns": [],
                "preview": []
            }
        
        preview = df.head(10).to_dict(orient='records')
        
        return {
            "filename": file.filename,
            "total_rows": len(df),
            "columns": list(df.columns),
            "preview": preview
        }

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)