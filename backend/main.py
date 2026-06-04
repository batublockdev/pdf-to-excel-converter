"""
PDF to Excel Converter - Backend v3.2
Modo Análisis: Extrae información real y la organiza
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
from collections import Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDF to Excel Converter",
    version="3.2.0"
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
    try:
        import pikepdf
        try:
            pdf = pikepdf.open(pdf_path)
            pdf.close()
            return pdf_path
        except pikepdf.PasswordError:
            pass
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
        return try_ghostscript_decrypt(pdf_path, password)


def try_ghostscript_decrypt(pdf_path: str, password: str = None) -> str:
    import subprocess
    output_path = pdf_path.replace('.pdf', '_decrypted.pdf')
    cmd = ['gs', '-q', '-dNOPAUSE', '-dBATCH', '-sDEVICE=pdfwrite', '-sOutputFile=' + output_path]
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
    try:
        import pikepdf
        try:
            pdf = pikepdf.open(pdf_path)
            pdf.close()
            return False
        except pikepdf.PasswordError:
            return True
    except ImportError:
        import subprocess
        result = subprocess.run(['pdfinfo', pdf_path], capture_output=True, text=True)
        return 'Encrypted' in result.stdout or 'password' in result.stderr.lower()


def ocr_space_extract(pdf_path: str) -> str:
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


# === ANÁLISIS INTELIGENTE ===

def parse_value(text: str) -> float:
    """Extrae valor numérico de un texto"""
    if not text:
        return 0.0
    # Eliminar símbolos de moneda y espacios
    text = str(text).replace('$', '').replace('€', '').replace(',', '').replace('.', '')
    text = text.replace(' ', '').replace('\t', '').replace('\n', '')
    # Buscar números
    numbers = re.findall(r'-?\d+', text)
    if numbers:
        try:
            return float(numbers[0])
        except:
            return 0.0
    return 0.0


def extract_all_values(df: pd.DataFrame, text: str) -> list:
    """Extrae todos los valores numéricos del documento"""
    values = []
    
    # Del DataFrame
    for col in df.columns:
        for val in df[col]:
            num = parse_value(str(val))
            if num != 0:
                values.append(num)
    
    # Del texto
    for line in text.split('\n'):
        num = parse_value(line)
        if num != 0:
            values.append(num)
    
    return values


def analyze_data(df: pd.DataFrame, text: str) -> dict:
    """Analiza los datos extraídos y organiza la información"""
    
    analysis = {
        'tipo_documento': 'Documento',
        'total_filas': len(df),
        'total_columnas': len(df.columns),
        'columnas': [],
        'resumen': {},
        'datos_importantes': [],
        'valores_encontrados': [],
        'categorias': {},
        'texto_completo': text[:5000] if text else ''
    }
    
    # Detectar tipo de documento
    text_lower = text.lower()
    
    # Detectar banco
    bancos = ['bancolombia', 'davivienda', 'bbva', 'banco de bogotá', 'banco de occidente',
              'banco popular', 'avianca', 'scotiabank', 'itau', 'citibank', 'santander',
              'extracto', 'estado de cuenta', 'cuenta de ahorros', 'cuenta corriente',
              'saldo', 'movimiento', 'transaccion']
    if any(b in text_lower for b in bancos):
        analysis['tipo_documento'] = 'Extracto Bancario'
    
    # Detectar factura de servicios
    servicios = ['epm', 'empresas públicas', 'gas natural', 'claro', 'movistar', 'tigo',
                 'factura', 'consumo', 'lectura', 'cargo fijo', 'energía', 'acueducto',
                 'alcantarillado', 'servicio público']
    if any(s in text_lower for s in servicios):
        analysis['tipo_documento'] = 'Factura de Servicios'
    
    # Detectar factura comercial
    if any(k in text_lower for k in ['factura', 'nit', 'subtotal', 'iva', 'total']):
        if analysis['tipo_documento'] == 'Documento':
            analysis['tipo_documento'] = 'Factura Comercial'
    
    # Analizar columnas
    for col in df.columns:
        col_data = {
            'nombre': col,
            'tipo': 'texto',
            'ejemplos': [],
            'valores_unicos': 0,
            'tiene_numeros': False,
            'tiene_fechas': False
        }
        
        sample = df[col].dropna().head(5).astype(str).tolist()
        col_data['ejemplos'] = sample
        
        # Detectar tipo de columna
        col_str = df[col].astype(str).str.cat(sep=' ')
        
        # Fechas
        if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', col_str):
            col_data['tiene_fechas'] = True
            col_data['tipo'] = 'fecha'
        
        # Valores monetarios
        if re.search(r'\$|[\d,]+\.\d{2}', col_str):
            col_data['tiene_numeros'] = True
            col_data['tipo'] = 'valor'
        
        # Contar valores únicos
        col_data['valores_unicos'] = df[col].nunique()
        
        analysis['columnas'].append(col_data)
    
    # Extraer valores numéricos importantes
    all_values = extract_all_values(df, text)
    if all_values:
        # Filtrar valores razonables (entre 100 y 100 millones)
        valores_filtrados = [v for v in all_values if 100 <= abs(v) <= 100000000]
        if valores_filtrados:
            analysis['valores_encontrados'] = sorted(set(valores_filtrados), reverse=True)[:20]
            analysis['resumen']['valor_maximo'] = max(valores_filtrados)
            analysis['resumen']['valor_minimo'] = min(valores_filtrados)
            analysis['resumen']['total_valores'] = len(valores_filtrados)
    
    # Buscar totales en el texto
    totales_pattern = r'(?:total|subtotal|saldo|cargo|abono|consumo)[:\s]*\$?\s*([\d.,]+)'
    totales = re.findall(totales_pattern, text_lower)
    if totales:
        analysis['datos_importantes'].extend([
            {'concepto': 'Total encontrado', 'valor': t}
            for t in totales[:5]
        ])
    
    # Buscar fechas
    fechas = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text)
    if fechas:
        fechas_unicas = list(set(fechas))[:10]
        analysis['datos_importantes'].append({
            'concepto': 'Fechas encontradas',
            'valor': ', '.join(fechas_unicas)
        })
    
    # Buscar NIT/cédulas
    nits = re.findall(r'\d{8,15}', text)
    if nits:
        nits_unicos = list(set(nits))[:5]
        analysis['datos_importantes'].append({
            'concepto': 'Números de identificación',
            'valor': ', '.join(nits_unicos)
        })
    
    # Categorizar filas por palabras clave
    categorias = {}
    keywords_categoria = {
        'Ingresos': ['abono', 'deposito', 'pago recibido', 'transferencia recibida', 'salario'],
        'Gastos': ['compra', 'pago', 'retiro', 'consumo', 'cargo'],
        'Servicios': ['energia', 'agua', 'gas', 'internet', 'telefono', 'celular'],
        'Alimentación': ['restaurante', 'cafe', 'mercado', 'supermercado'],
        'Transporte': ['uber', 'taxi', 'gasolina', 'metro', 'bus'],
    }
    
    for col in df.columns:
        for idx, val in df[col].items():
            val_str = str(val).lower()
            for cat, keywords in keywords_categoria.items():
                if any(kw in val_str for kw in keywords):
                    if cat not in categorias:
                        categorias[cat] = []
                    categorias[cat].append(str(val))
    
    analysis['categorias'] = categorias
    
    return analysis


def create_analysis_excel(df_raw: pd.DataFrame, analysis: dict) -> BytesIO:
    """Crea Excel organizado con la información encontrada"""
    
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        
        # Hoja 1: Resumen del Documento
        resumen_rows = [
            ['INFORMACIÓN DEL DOCUMENTO'],
            ['Tipo de documento:', analysis.get('tipo_documento', 'Documento')],
            ['Total filas:', analysis.get('total_filas', 0)],
            ['Total columnas:', analysis.get('total_columnas', 0)],
            ['']
        ]
        
        # Agregar datos importantes
        if analysis.get('datos_importantes'):
            resumen_rows.append(['DATOS IMPORTANTES:'])
            for dato in analysis['datos_importantes']:
                resumen_rows.append([dato.get('concepto', ''), dato.get('valor', '')])
            resumen_rows.append([''])
        
        # Agregar valores encontrados
        if analysis.get('valores_encontrados'):
            resumen_rows.append(['VALORES ENCONTRADOS:'])
            resumen_rows.append(['Valores principales:', ', '.join(map(str, analysis['valores_encontrados'][:10]))])
            if 'valor_maximo' in analysis.get('resumen', {}):
                resumen_rows.append(['Valor máximo:', f"${analysis['resumen']['valor_maximo']:,.0f}"])
            if 'valor_minimo' in analysis.get('resumen', {}):
                resumen_rows.append(['Valor mínimo:', f"${analysis['resumen']['valor_minimo']:,.0f}"])
            resumen_rows.append([''])
        
        # Agregar categorías
        if analysis.get('categorias'):
            resumen_rows.append(['CATEGORÍAS ENCONTRADAS:'])
            for cat, items in analysis['categorias'].items():
                resumen_rows.append([f'{cat} ({len(items)} items):', items[0] if items else ''])
            resumen_rows.append([''])
        
        # Agregar columnas detectadas
        if analysis.get('columnas'):
            resumen_rows.append(['COLUMNAS DETECTADAS:'])
            for col in analysis['columnas'][:5]:  # Primeras 5 columnas
                resumen_rows.append([col['nombre'], f"Tipo: {col['tipo']}, Ejemplos: {', '.join(str(x) for x in col['ejemplos'][:3])}"])
        
        df_resumen = pd.DataFrame(resumen_rows)
        df_resumen.to_excel(writer, sheet_name='Resumen', index=False, header=False)
        
        # Hoja 2: Categorías (si hay)
        if analysis.get('categorias'):
            cat_rows = []
            for cat, items in analysis['categorias'].items():
                for item in items[:50]:  # Máximo 50 items por categoría
                    cat_rows.append({'Categoría': cat, 'Contenido': item})
            if cat_rows:
                df_cat = pd.DataFrame(cat_rows)
                df_cat.to_excel(writer, sheet_name='Categorías', index=False)
        
        # Hoja 3: Datos Completos (raw)
        df_raw.to_excel(writer, sheet_name='Datos_Completos', index=False)
        
        # Hoja 4: Texto extraído (si hay)
        if analysis.get('texto_completo'):
            df_texto = pd.DataFrame({'Texto': analysis['texto_completo'].split('\n')})
            df_texto.to_excel(writer, sheet_name='Texto_Extraído', index=False)
        
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
                adjusted_width = min(max_length + 2, 80)
                ws.column_dimensions[column].width = adjusted_width
    
    output.seek(0)
    return output


@app.get("/")
async def root():
    return {
        "message": "PDF to Excel Converter API",
        "version": "3.2.0",
        "status": "running",
        "features": ["ocr", "password_support", "analysis_mode", "auto_detection"]
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/convert")
async def convert_pdf(
    file: UploadFile = File(...),
    password: str = Form(None),
    mode: str = Form("raw")
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
        text, tables, words = extract_with_pdfplumber(tmp_path)
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
            analysis = analyze_data(df, text)
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