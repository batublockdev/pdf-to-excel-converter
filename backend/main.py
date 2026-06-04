"""
PDF to Excel Converter - Backend v2.2
Convierte cualquier PDF a Excel, incluyendo PDFs escaneados (OCR)
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import pandas as pd
from io import BytesIO
import tempfile
import os
import logging
import re
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDF to Excel Converter",
    version="2.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OCR.space API (Free: 25,000 requests/mes)
OCR_SPACE_API_KEY = "K87736648888957"


def get_column_letter(idx: int) -> str:
    result = ""
    idx += 1
    while idx > 0:
        idx -= 1
        result = chr(65 + idx % 26) + result
        idx //= 26
    return result


def ocr_space_extract(pdf_path: str) -> str:
    """Extrae texto de PDF usando OCR.space API"""
    try:
        with open(pdf_path, 'rb') as f:
            response = requests.post(
                'https://api.ocr.space/parse/image',
                files={'file': f},
                data={
                    'apikey': OCR_SPACE_API_KEY,
                    'language': 'spa',
                    'isOverlayRequired': 'false',
                    'OCREngine': '2',
                },
                timeout=60
            )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('OCRExitCode') == 1:
                parsed = result.get('ParsedResults', [])
                if parsed:
                    return parsed[0].get('ParsedText', '')
        return ""
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return ""


def extract_with_pdfplumber(pdf_path: str) -> tuple:
    """Intenta extraer con pdfplumber, retorna (texto, tablas, words)"""
    text = ""
    tables = []
    words = []
    
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # Texto
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                
                # Tablas
                try:
                    page_tables = page.extract_tables()
                    tables.extend(page_tables)
                except:
                    pass
                
                # Palabras
                try:
                    page_words = page.extract_words()
                    words.extend(page_words)
                except:
                    pass
    except Exception as e:
        logger.warning(f"pdfplumber falló: {e}")
    
    return text, tables, words


def text_to_dataframe(text: str) -> pd.DataFrame:
    """Convierte texto a DataFrame"""
    if not text:
        return pd.DataFrame()
    
    lines = text.split('\n')
    all_rows = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = re.split(r'\s{2,}', line)
        parts = [p.strip() for p in parts if p.strip()]
        if parts:
            all_rows.append(parts)
    
    if not all_rows:
        return pd.DataFrame()
    
    max_cols = max(len(row) for row in all_rows)
    
    normalized = []
    for row in all_rows:
        if len(row) < max_cols:
            row = list(row) + [''] * (max_cols - len(row))
        normalized.append(row[:max_cols])
    
    df = pd.DataFrame(normalized)
    df.columns = [f"Columna_{i+1}" for i in range(len(df.columns))]
    
    return df


def tables_to_dataframe(tables: list) -> pd.DataFrame:
    """Convierte tablas a DataFrame"""
    if not tables:
        return pd.DataFrame()
    
    all_rows = []
    for table in tables:
        if not table:
            continue
        for row in table:
            clean_row = [str(cell).strip() if cell else '' for cell in row]
            if any(clean_row):
                all_rows.append(clean_row)
    
    if not all_rows:
        return pd.DataFrame()
    
    max_cols = max(len(row) for row in all_rows)
    
    normalized = []
    for row in all_rows:
        if len(row) < max_cols:
            row = list(row) + [''] * (max_cols - len(row))
        normalized.append(row[:max_cols])
    
    df = pd.DataFrame(normalized)
    df.columns = [f"Columna_{i+1}" for i in range(len(df.columns))]
    
    return df


def words_to_dataframe(words: list) -> pd.DataFrame:
    """Convierte palabras con posición a DataFrame"""
    if not words:
        return pd.DataFrame()
    
    # Agrupar por línea Y
    lines = {}
    for word in words:
        y = round(word['top'], -1)
        if y not in lines:
            lines[y] = []
        lines[y].append(word)
    
    all_rows = []
    for y in sorted(lines.keys()):
        line_words = sorted(lines[y], key=lambda w: w['x0'])
        row = [w['text'] for w in line_words]
        if row:
            all_rows.append(row)
    
    if not all_rows:
        return pd.DataFrame()
    
    max_cols = max(len(row) for row in all_rows)
    
    normalized = []
    for row in all_rows:
        if len(row) < max_cols:
            row = list(row) + [''] * (max_cols - len(row))
        normalized.append(row[:max_cols])
    
    df = pd.DataFrame(normalized)
    df.columns = [f"Columna_{i+1}" for i in range(len(df.columns))]
    
    return df


def smart_extract(pdf_path: str) -> pd.DataFrame:
    """Extrae datos usando múltiples métodos"""
    
    # Intentar con pdfplumber primero
    text, tables, words = extract_with_pdfplumber(pdf_path)
    
    # Crear DataFrames de cada método
    df_tables = tables_to_dataframe(tables)
    df_text = text_to_dataframe(text)
    df_words = words_to_dataframe(words)
    
    # Si pdfplumber no extrajo nada, usar OCR
    total_rows = len(df_tables) + len(df_text) + len(df_words)
    
    if total_rows == 0:
        logger.info("pdfplumber no extrajo datos, usando OCR...")
        ocr_text = ocr_space_extract(pdf_path)
        if ocr_text:
            df_ocr = text_to_dataframe(ocr_text)
            if not df_ocr.empty:
                logger.info(f"OCR extrajo {len(df_ocr)} filas")
                return df_ocr
    
    # Elegir el mejor resultado
    results = [
        ('tables', df_tables, len(df_tables)),
        ('text', df_text, len(df_text)),
        ('words', df_words, len(df_words))
    ]
    
    results.sort(key=lambda x: x[2], reverse=True)
    
    best_method, best_df, _ = results[0]
    
    if best_df.empty:
        # Último recurso: OCR
        logger.info("Intentando OCR como último recurso...")
        ocr_text = ocr_space_extract(pdf_path)
        if ocr_text:
            return text_to_dataframe(ocr_text)
        return pd.DataFrame()
    
    logger.info(f"Mejor método: {best_method} con {len(best_df)} filas")
    return best_df


@app.get("/")
async def root():
    return {"message": "PDF to Excel Converter API", "version": "2.2.0", "status": "running", "ocr": "enabled"}


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
    except HTTPException:
        raise
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

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Datos')
            
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
    except HTTPException:
        raise
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