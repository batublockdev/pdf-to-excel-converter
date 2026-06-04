"""
PDF to Excel Converter - Backend v2.1
Convierte cualquier PDF a Excel, incluyendo PDFs escaneados (OCR)
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
import requests
from PIL import Image
import pdf2image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDF to Excel Converter",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OCR.space API (Free: 25,000 requests/mes)
OCR_SPACE_API_KEY = "K87736648888957"  # Free public key


def get_column_letter(idx: int) -> str:
    result = ""
    idx += 1
    while idx > 0:
        idx -= 1
        result = chr(65 + idx % 26) + result
        idx //= 26
    return result


def ocr_space_extract(pdf_path: str) -> str:
    """Extrae texto de PDF escaneado usando OCR.space API"""
    try:
        with open(pdf_path, 'rb') as f:
            response = requests.post(
                'https://api.ocr.space/parse/image',
                files={'file': f},
                data={
                    'apikey': OCR_SPACE_API_KEY,
                    'language': 'spa',  # Español
                    'isOverlayRequired': 'false',
                    'OCREngine': '2',  # Engine más preciso
                },
                timeout=60
            )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('OCRExitCode') == 1:
                text = result.get('ParsedResults', [{}])[0].get('ParsedText', '')
                return text
        return ""
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return ""


def is_scanned_pdf(pdf_path: str) -> bool:
    """Detecta si un PDF es escaneado (solo imágenes)"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:2]:
                text = page.extract_text()
                if text and len(text.strip()) > 50:
                    return False
        return True
    except:
        return True


def extract_all_text_structured(pdf_path: str) -> pd.DataFrame:
    """Extrae TODO el texto y lo organiza"""
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
                parts = re.split(r'\s{2,}', line)
                parts = [p.strip() for p in parts if p.strip()]
                if parts:
                    all_lines.append(parts)
    
    if not all_lines:
        return pd.DataFrame()
    
    max_parts = max(len(line) for line in all_lines)
    
    rows = []
    for line in all_lines:
        if len(line) < max_parts:
            line = list(line) + [''] * (max_parts - len(line))
        rows.append(line[:max_parts])
    
    df = pd.DataFrame(rows)
    df.columns = [f"Columna_{i+1}" for i in range(len(df.columns))]
    
    return df


def extract_with_words(pdf_path: str) -> pd.DataFrame:
    """Extrae usando posiciones de palabras"""
    all_rows = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue
            
            lines = {}
            for word in words:
                y = round(word['top'], -1)
                if y not in lines:
                    lines[y] = []
                lines[y].append(word)
            
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


def extract_tables_traditional(pdf_path: str) -> pd.DataFrame:
    """Extrae tablas tradicionales"""
    all_tables = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            try:
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) >= 2:
                        for row in table:
                            clean_row = [str(cell).strip() if cell else '' for cell in row]
                            if any(clean_row):
                                all_tables.append(clean_row)
            except:
                continue
    
    if not all_tables:
        return pd.DataFrame()
    
    max_cols = max(len(row) for row in all_tables)
    
    normalized = []
    for row in all_tables:
        if len(row) < max_cols:
            row = list(row) + [''] * (max_cols - len(row))
        normalized.append(row[:max_cols])
    
    df = pd.DataFrame(normalized)
    df.columns = [f"Columna_{i+1}" for i in range(len(df.columns))]
    
    return df


def ocr_text_to_dataframe(text: str) -> pd.DataFrame:
    """Convierte texto OCR a DataFrame"""
    if not text:
        return pd.DataFrame()
    
    lines = text.split('\n')
    all_rows = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Separar por espacios múltiples
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


def smart_extract(pdf_path: str) -> pd.DataFrame:
    """Extrae datos usando múltiples métodos, incluyendo OCR"""
    
    # Verificar si es PDF escaneado
    is_scanned = is_scanned_pdf(pdf_path)
    logger.info(f"PDF escaneado: {is_scanned}")
    
    if is_scanned:
        logger.info("Usando OCR para PDF escaneado...")
        text = ocr_space_extract(pdf_path)
        if text:
            df = ocr_text_to_dataframe(text)
            if not df.empty:
                logger.info(f"OCR extrajo {len(df)} filas")
                return df
    
    # Métodos tradicionales para PDFs con texto
    df_tables = extract_tables_traditional(pdf_path)
    df_text = extract_all_text_structured(pdf_path)
    df_words = extract_with_words(pdf_path)
    
    results = [
        ('tables', df_tables, len(df_tables) if not df_tables.empty else 0),
        ('text', df_text, len(df_text) if not df_text.empty else 0),
        ('words', df_words, len(df_words) if not df_words.empty else 0)
    ]
    
    results.sort(key=lambda x: x[2], reverse=True)
    
    best_method, best_df, _ = results[0]
    
    if best_df.empty:
        return pd.DataFrame()
    
    logger.info(f"Mejor método: {best_method} con {len(best_df)} filas")
    
    return best_df


@app.get("/")
async def root():
    return {"message": "PDF to Excel Converter API", "version": "2.1.0", "status": "running", "ocr": "enabled"}


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
            raise HTTPException(status_code=400, detail="No se pudo extraer contenido del PDF. Si es un PDF escaneado, asegúrate de que tenga buena calidad.")

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