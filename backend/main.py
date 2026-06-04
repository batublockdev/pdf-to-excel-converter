"""
PDF to Excel Converter - Backend v3.0
Convierte cualquier PDF a Excel con 2 modos: Raw y Análisis
Soporta PDFs protegidos con contraseña
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
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
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OCR.space API
OCR_SPACE_API_KEY = "K87736648888957"


def get_column_letter(idx: int) -> str:
    result = ""
    idx += 1
    while idx > 0:
        idx -= 1
        result = chr(65 + idx % 26) + result
        idx //= 26
    return result


def decrypt_pdf(pdf_path: str, password: str = None) -> str:
    """Intenta desencriptar un PDF con contraseña"""
    try:
        import pikepdf
        
        # Intentar abrir sin password
        try:
            pdf = pikepdf.open(pdf_path)
            pdf.close()
            return pdf_path
        except pikepdf.PasswordError:
            pass
        
        # Intentar con password proporcionado
        if password:
            try:
                pdf = pikepdf.open(pdf_path, password=password)
                decrypted_path = pdf_path.replace('.pdf', '_decrypted.pdf')
                pdf.save(decrypted_path)
                pdf.close()
                return decrypted_path
            except pikepdf.PasswordError:
                return None
        
        return None
    except ImportError:
        # pikepdf no instalado, intentar con ghostscript
        return try_ghostscript_decrypt(pdf_path, password)


def try_ghostscript_decrypt(pdf_path: str, password: str = None) -> str:
    """Intenta desencriptar con Ghostscript"""
    import subprocess
    
    output_path = pdf_path.replace('.pdf', '_decrypted.pdf')
    
    cmd = [
        'gs', '-q', '-dNOPAUSE', '-dBATCH', '-sDEVICE=pdfwrite',
        '-sOutputFile=' + output_path
    ]
    
    if password:
        cmd.append(f'-sPDFPassword={password}')
    
    cmd.append(pdf_path)
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode == 0 and os.path.exists(output_path):
            return output_path
    except:
        pass
    
    return None


def is_encrypted(pdf_path: str) -> bool:
    """Detecta si un PDF está encriptado"""
    try:
        import pikepdf
        try:
            pdf = pikepdf.open(pdf_path)
            pdf.close()
            return False
        except pikepdf.PasswordError:
            return True
    except ImportError:
        # Fallback: intentar con pdfinfo
        import subprocess
        result = subprocess.run(['pdfinfo', pdf_path], capture_output=True, text=True)
        return 'Encrypted' in result.stdout or 'password' in result.stderr.lower()


def ocr_space_extract(pdf_path: str) -> str:
    """Extrae texto usando OCR.space API"""
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
    """Extrae datos con pdfplumber"""
    text = ""
    tables = []
    words = []
    
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                
                try:
                    page_tables = page.extract_tables()
                    tables.extend(page_tables)
                except:
                    pass
                
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
    
    text, tables, words = extract_with_pdfplumber(pdf_path)
    
    df_tables = tables_to_dataframe(tables)
    df_text = text_to_dataframe(text)
    df_words = words_to_dataframe(words)
    
    total_rows = len(df_tables) + len(df_text) + len(df_words)
    
    if total_rows == 0:
        logger.info("Usando OCR...")
        ocr_text = ocr_space_extract(pdf_path)
        if ocr_text:
            return text_to_dataframe(ocr_text)
    
    results = [
        ('tables', df_tables, len(df_tables)),
        ('text', df_text, len(df_text)),
        ('words', df_words, len(df_words))
    ]
    
    results.sort(key=lambda x: x[2], reverse=True)
    
    best_method, best_df, _ = results[0]
    
    if best_df.empty:
        ocr_text = ocr_space_extract(pdf_path)
        if ocr_text:
            return text_to_dataframe(ocr_text)
        return pd.DataFrame()
    
    logger.info(f"Mejor método: {best_method} con {len(best_df)} filas")
    return best_df


# === MODO ANÁLISIS ===

def parse_currency(value: str) -> float:
    """Convierte string de moneda a float"""
    if not value:
        return 0.0
    
    # Limpiar
    value = value.replace('$', '').replace(',', '').replace('.', '')
    value = value.replace(' ', '').replace('\t', '')
    
    # Detectar signo
    sign = -1 if '-' in value or '(' in value else 1
    
    # Extraer números
    numbers = re.findall(r'\d+', value)
    if numbers:
        return sign * float(''.join(numbers))
    return 0.0


def detect_transaction_type(text: str) -> str:
    """Detecta si es ingreso o gasto"""
    text = text.lower()
    
    gastos_keywords = ['compra', 'pago', 'retiro', 'transferencia', 'giro', 'carga', 'consumo', 'pse', 'nequi', 'daviplata', 'bancolombia', 'davivienda']
    ingresos_keywords = ['abono', 'transferencia recibida', 'depósito', 'pago recibido', 'devolución', 'reembolso']
    
    for kw in ingresos_keywords:
        if kw in text:
            return 'INGRESO'
    
    for kw in gastos_keywords:
        if kw in text:
            return 'GASTO'
    
    return 'OTRO'


def categorize_transaction(description: str) -> str:
    """Categoriza una transacción"""
    desc = description.lower()
    
    categorias = {
        'Comida': ['restaurante', 'café', 'pizza', 'hamburguesa', 'sushi', 'comida', 'almuerzo', 'cena', 'domicilios', 'rappi', 'uber eats', 'menu'],
        'Transporte': ['uber', 'taxi', 'metro', 'bus', 'gasolina', ' parqueadero', 'peaje', 'transmilenio'],
        'Entretenimiento': ['netflix', 'spotify', 'prime', 'cine', 'concierto', 'teatro', 'youtube', 'disney'],
        'Compras': ['amazon', 'mercado', 'exito', 'd1', 'ara', 'justo', 'super', 'tienda', 'ropa', 'falabella'],
        'Servicios': ['luz', 'agua', 'gas', 'internet', 'celular', 'telefono', 'epm', 'claro', 'movistar', 'tigo'],
        'Salud': ['farmacia', 'medico', 'clinica', 'eps', 'drogueria', 'laboratorio'],
        'Educacion': ['curso', 'universidad', 'colegio', 'libro', 'udemy', 'coursera'],
        'Transferencias': ['nequi', 'daviplata', 'pse', 'transfer', 'bancolombia', 'davivienda', 'bbva'],
        'Suscripciones': ['netflix', 'spotify', 'prime', 'youtube premium', 'icloud', 'dropbox'],
    }
    
    for categoria, keywords in categorias.items():
        for kw in keywords:
            if kw in desc:
                return categoria
    
    return 'Otros'


def analyze_transactions(df: pd.DataFrame) -> dict:
    """Analiza transacciones y extrae información financiera"""
    
    transactions = []
    total_ingresos = 0.0
    total_gastos = 0.0
    
    # Buscar columnas con valores monetarios
    value_columns = []
    for col in df.columns:
        sample = df[col].dropna().head(20).astype(str)
        currency_pattern = sample.str.contains(r'\$|[\d,]+\.\d{2}', regex=True)
        if currency_pattern.sum() > len(sample) * 0.3:
            value_columns.append(col)
    
    # Buscar columna de descripción
    desc_col = None
    for col in df.columns:
        sample = df[col].dropna().head(20).astype(str)
        if sample.str.len().mean() > 15:  # Descripciones suelen ser más largas
            desc_col = col
            break
    
    # Buscar columna de fecha
    date_col = None
    for col in df.columns:
        sample = df[col].dropna().head(20).astype(str)
        date_pattern = sample.str.contains(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}', regex=True)
        if date_pattern.sum() > len(sample) * 0.3:
            date_col = col
            break
    
    # Extraer transacciones
    for idx, row in df.iterrows():
        # Buscar valores monetarios
        for col in value_columns:
            value = parse_currency(str(row[col]))
            if value != 0:
                description = str(row[desc_col]) if desc_col else 'Sin descripción'
                date = str(row[date_col]) if date_col else ''
                
                tipo = detect_transaction_type(description)
                categoria = categorize_transaction(description)
                
                transactions.append({
                    'Fecha': date,
                    'Descripción': description[:100],  # Limitar longitud
                    'Tipo': tipo,
                    'Categoría': categoria,
                    'Valor': value
                })
                
                if tipo == 'INGRESO':
                    total_ingresos += abs(value)
                elif tipo == 'GASTO':
                    total_gastos += abs(value)
                
                break  # Solo un valor por fila
    
    return {
        'transactions': transactions,
        'total_ingresos': total_ingresos,
        'total_gastos': total_gastos,
        'balance': total_ingresos - total_gastos
    }


def create_analysis_excel(df_raw: pd.DataFrame, analysis: dict) -> BytesIO:
    """Crea Excel con análisis financiero"""
    
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        
        # Hoja 1: Resumen
        resumen_data = {
            'Concepto': ['Total Ingresos', 'Total Gastos', 'Balance', '', 'Categoría', ''],
            'Valor': [
                f"${analysis['total_ingresos']:,.0f}",
                f"${analysis['total_gastos']:,.0f}",
                f"${analysis['balance']:,.0f}",
                '',
                'Top Categorías',
                ''
            ]
        }
        
        # Contar por categoría
        from collections import Counter
        categorias = Counter([t['Categoría'] for t in analysis['transactions']])
        for cat, count in categorias.most_common(10):
            resumen_data['Concepto'].append(cat)
            resumen_data['Valor'].append(count)
        
        df_resumen = pd.DataFrame(resumen_data)
        df_resumen.to_excel(writer, sheet_name='Resumen', index=False)
        
        # Hoja 2: Transacciones
        if analysis['transactions']:
            df_trans = pd.DataFrame(analysis['transactions'])
            df_trans.to_excel(writer, sheet_name='Transacciones', index=False)
        else:
            pd.DataFrame({'Info': ['No se detectaron transacciones']}).to_excel(
                writer, sheet_name='Transacciones', index=False
            )
        
        # Hoja 3: Datos Raw
        df_raw.to_excel(writer, sheet_name='Datos_Completos', index=False)
        
        # Formatear
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column].width = adjusted_width
    
    output.seek(0)
    return output


@app.get("/")
async def root():
    return {
        "message": "PDF to Excel Converter API",
        "version": "3.0.0",
        "status": "running",
        "features": ["ocr", "password_support", "analysis_mode"]
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/convert")
async def convert_pdf(
    file: UploadFile = File(...),
    password: str = Form(None),
    mode: str = Form("raw")  # "raw" o "analysis"
):
    logger.info(f"Recibiendo: {file.filename}, modo: {mode}")

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
        # Verificar encriptación
        if is_encrypted(tmp_path):
            if not password:
                raise HTTPException(
                    status_code=400,
                    detail="Este PDF está protegido con contraseña. Por favor proporciona el password."
                )
            
            decrypted_path = decrypt_pdf(tmp_path, password)
            if not decrypted_path:
                raise HTTPException(
                    status_code=400,
                    detail="No se pudo desencriptar el PDF. Verifica la contraseña."
                )
            
            if decrypted_path != tmp_path:
                os.unlink(tmp_path)
                tmp_path = decrypted_path
        
        # Extraer datos
        df = smart_extract(tmp_path)
        
        if df.empty:
            raise HTTPException(status_code=400, detail="No se pudo extraer contenido del PDF")

        logger.info(f"Extraído: {len(df)} filas, {len(df.columns)} columnas")

        # Modo Raw
        if mode == "raw":
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
        
        # Modo Análisis
        else:
            analysis = analyze_transactions(df)
            output = create_analysis_excel(df, analysis)
            
            excel_filename = file.filename.replace('.pdf', '_analisis.xlsx')
            
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
async def preview_pdf(
    file: UploadFile = File(...),
    password: str = Form(None)
):
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
        # Verificar encriptación
        encrypted = is_encrypted(tmp_path)
        
        if encrypted:
            if password:
                decrypted_path = decrypt_pdf(tmp_path, password)
                if decrypted_path and decrypted_path != tmp_path:
                    os.unlink(tmp_path)
                    tmp_path = decrypted_path
                    encrypted = False
        
        if encrypted:
            return {
                "filename": file.filename,
                "encrypted": True,
                "total_rows": 0,
                "columns": [],
                "preview": []
            }
        
        df = smart_extract(tmp_path)
        
        if df.empty:
            return {
                "filename": file.filename,
                "encrypted": False,
                "total_rows": 0,
                "columns": [],
                "preview": []
            }
        
        preview = df.head(10).to_dict(orient='records')
        
        return {
            "filename": file.filename,
            "encrypted": False,
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