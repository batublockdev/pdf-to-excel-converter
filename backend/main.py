"""
PDF to Excel Converter - Backend v3.1
Convierte cualquier PDF a Excel con análisis inteligente dinámico
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
    version="3.1.0"
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
    """Intenta desencriptar con Ghostscript"""
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


# === ANÁLISIS INTELIGENTE DINÁMICO ===

def detect_document_type(text: str, df: pd.DataFrame) -> str:
    """Detecta el tipo de documento"""
    text_lower = text.lower()
    
    # Detectar banco/extracto bancario
    bancos = ['bancolombia', 'davivienda', 'bbva', 'banco de bogotá', 'banco de occidente',
              'banco popular', 'avianca', 'scotiabank', 'itau', 'popular', 'occidente',
              'bogota', 'citibank', 'santander', 'bank of america', 'chase', 'wells fargo',
              'extracto', 'estado de cuenta', 'cuenta de ahorros', 'cuenta corriente',
              'saldo anterior', 'saldo actual', 'movimientos', 'transacciones']
    
    for banco in bancos:
        if banco in text_lower:
            return 'extracto_bancario'
    
    # Detectar factura de servicios públicos
    servicios = ['epm', 'empresas públicas', 'gas natural', 'argos', 'claro', 'movistar',
                 'tigo', 'directv', 'netflix', 'spotify', 'factura', 'consumo', 'lectura',
                 'cargo fijo', 'subsidio', 'contribución', 'energía', 'acueducto',
                 'alcantarillado', 'aseo', 'servicio', 'pago', 'período']
    
    for servicio in servicios:
        if servicio in text_lower:
            return 'factura_servicios'
    
    # Detectar factura comercial
    factura_keywords = ['factura', 'nit', 'número de factura', 'fecha de emisión',
                        'subtotal', 'iva', 'impuesto', 'total', 'proveedor',
                        'cliente', 'vendedor', 'artículo', 'producto', 'cantidad',
                        'precio unitario', 'descuento']
    
    count_factura = sum(1 for kw in factura_keywords if kw in text_lower)
    if count_factura >= 3:
        return 'factura_comercial'
    
    # Detectar nómina
    nomina_keywords = ['nómina', 'nomina', 'salario', 'devengado', 'deducciones',
                       'seguridad social', 'pensión', 'salud', 'arl', 'cesantías',
                       'prima', 'vacaciones', 'auxilio', 'transporte']
    
    count_nomina = sum(1 for kw in nomina_keywords if kw in text_lower)
    if count_nomina >= 3:
        return 'nomina'
    
    # Detectar reporte/tabla genérica
    if len(df) > 10:
        return 'reporte'
    
    return 'documento_generico'


def parse_currency(value: str) -> float:
    """Convierte string de moneda a float"""
    if not value:
        return 0.0
    
    value = str(value).replace('$', '').replace('€', '').replace('USD', '')
    value = value.replace(',', '').replace('.', '').replace(' ', '')
    value = value.replace('\t', '').replace('\n', '')
    
    sign = -1 if '-' in value or '(' in value else 1
    numbers = re.findall(r'\d+', value)
    
    if numbers:
        return sign * float(''.join(numbers))
    return 0.0


def categorize_transaction(description: str) -> tuple:
    """Categoriza una transacción y devuelve (categoría, tipo)"""
    desc = description.lower()
    
    # Categorías y keywords
    categorias = {
        'Alimentación': ['restaurante', 'café', 'pizza', 'hamburguesa', 'sushi', 'comida',
                        'almuerzo', 'cena', 'domicilios', 'rappi', 'uber eats', 'menu',
                        'domicilio', 'mercado', 'supermercado', 'éxito', 'd1', 'ara',
                        'justo', 'comida', 'pan', 'postre'],
        
        'Transporte': ['uber', 'taxi', 'metro', 'bus', 'gasolina', 'parqueadero',
                      'peaje', 'transmilenio', 'transporte', 'siti', 'didi', 'cabify',
                      'combustible', 'carro', 'moto'],
        
        'Entretenimiento': ['netflix', 'spotify', 'prime', 'cine', 'concierto', 'teatro',
                          'youtube', 'disney', 'hbo', 'pelicula', 'series', 'musica',
                          'videojuego', 'playstation', 'xbox', 'steam'],
        
        'Compras': ['amazon', 'mercado', 'exito', 'falabella', 'alkosto', 'exito',
                   'tienda', 'ropa', 'zapatos', 'electronica', 'muebles'],
        
        'Servicios': ['luz', 'agua', 'gas', 'internet', 'celular', 'telefono', 'epm',
                     'claro', 'movistar', 'tigo', 'servicios', 'publicos'],
        
        'Salud': ['farmacia', 'medico', 'clinica', 'eps', 'drogueria', 'laboratorio',
                 'doctor', 'cita', 'medicamento', 'salud'],
        
        'Educación': ['curso', 'universidad', 'colegio', 'libro', 'udemy', 'coursera',
                     'escuela', 'estudio', 'clase', 'diplomado'],
        
        'Transferencias': ['nequi', 'daviplata', 'pse', 'transfer', 'bancolombia',
                          'davivienda', 'bbva', 'banco', 'envio', 'recibido'],
        
        'Ingresos': ['salario', 'nomina', 'abono', 'deposito', 'pago recibido',
                    'transferencia recibida', 'devolucion', 'reembolso', 'comision',
                    'honorario', 'venta'],
        
        'Impuestos': ['impuesto', 'iva', 'retefuente', 'reteiva', 'predial', 'vehiculo',
                      'declaracion', 'dian', 'renta'],
        
        'Hogar': ['arriendo', 'alquiler', 'mantenimiento', 'reparacion', 'hogar',
                 'muebles', 'electrodomestico', 'cocina'],
    }
    
    # Detectar tipo primero
    tipo = 'GASTO'
    ingresos_keywords = ['abono', 'deposito', 'recibido', 'salario', 'nomina',
                        'devolucion', 'reembolso', 'transferencia recibida']
    for kw in ingresos_keywords:
        if kw in desc:
            tipo = 'INGRESO'
            break
    
    # Detectar categoría
    for categoria, keywords in categorias.items():
        for kw in keywords:
            if kw in desc:
                return categoria, tipo
    
    return 'Otros', tipo


def analyze_bank_statement(df: pd.DataFrame, text: str) -> dict:
    """Analiza un extracto bancario"""
    transactions = []
    total_ingresos = 0.0
    total_gastos = 0.0
    
    # Buscar columnas con valores monetarios
    value_cols = []
    date_cols = []
    desc_cols = []
    
    for col in df.columns:
        sample = df[col].dropna().head(20).astype(str)
        
        # Detectar columna de valores
        currency_count = sample.str.contains(r'\$|[\d,]+\.\d{2}', regex=True).sum()
        if currency_count > len(sample) * 0.3:
            value_cols.append(col)
        
        # Detectar columna de fechas
        date_count = sample.str.contains(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', regex=True).sum()
        if date_count > len(sample) * 0.3:
            date_cols.append(col)
        
        # Detectar columna de descripción (texto más largo)
        avg_len = sample.str.len().mean()
        if avg_len > 15:
            desc_cols.append(col)
    
    # Extraer transacciones
    desc_col = desc_cols[0] if desc_cols else df.columns[0]
    
    for idx, row in df.iterrows():
        for col in value_cols:
            value = parse_currency(str(row[col]))
            if value != 0:
                description = str(row[desc_col]) if desc_col in row.index else 'Sin descripción'
                fecha = ''
                for dc in date_cols:
                    fecha = str(row[dc])
                    break
                
                categoria, tipo = categorize_transaction(description)
                
                transactions.append({
                    'Fecha': fecha,
                    'Descripción': description[:100],
                    'Tipo': tipo,
                    'Categoría': categoria,
                    'Valor': value
                })
                
                if tipo == 'INGRESO':
                    total_ingresos += abs(value)
                else:
                    total_gastos += abs(value)
                
                break  # Solo un valor por fila
    
    # Categorizar gastos
    gastos_por_categoria = Counter()
    for t in transactions:
        if t['Tipo'] == 'GASTO':
            gastos_por_categoria[t['Categoría']] += abs(t['Valor'])
    
    return {
        'tipo_documento': 'Extracto Bancario',
        'transactions': transactions,
        'resumen': {
            'total_ingresos': total_ingresos,
            'total_gastos': total_gastos,
            'balance': total_ingresos - total_gastos,
            'num_transacciones': len(transactions)
        },
        'gastos_por_categoria': dict(gastos_por_categoria.most_common(10))
    }


def analyze_utility_bill(df: pd.DataFrame, text: str) -> dict:
    """Analiza una factura de servicios públicos"""
    data = {
        'tipo_documento': 'Factura de Servicios',
        'datos_generales': {},
        'conceptos': [],
        'totales': {}
    }
    
    text_lower = text.lower()
    
    # Detectar tipo de servicio
    if 'energ' in text_lower or 'electricidad' in text_lower or 'epm' in text_lower:
        data['servicio'] = 'Energía'
    elif 'acueducto' in text_lower or 'agua' in text_lower:
        data['servicio'] = 'Acueducto'
    elif 'gas' in text_lower:
        data['servicio'] = 'Gas Natural'
    elif 'alcantarillado' in text_lower:
        data['servicio'] = 'Alcantarillado'
    elif 'aseo' in text_lower or 'basura' in text_lower:
        data['servicio'] = 'Aseo'
    
    # Extraer conceptos comunes
    conceptos_patterns = {
        'consumo': r'consumo\s+(\w+-\w+)\s+(\d+)\s+([\d.,]+)',
        'cargo_fijo': r'cargo\s+fijo\s+(\w+-\w+)\s+([\d.,]+)',
        'subsidio': r'subsidio\s+(-?[\d.,]+)',
        'total': r'total\s+(\w+)?\s*\$?\s*([\d.,]+)',
    }
    
    for concepto, pattern in conceptos_patterns.items():
        matches = re.findall(pattern, text_lower)
        if matches:
            data['conceptos'].append({
                'nombre': concepto.replace('_', ' ').title(),
                'valores': matches
            })
    
    # Buscar totales
    total_match = re.search(r'total\s+(\w+)?\s*\$?\s*([\d.,]+)', text_lower)
    if total_match:
        data['totales']['total'] = total_match.group(2).replace('.', '').replace(',', '.')
    
    return data


def analyze_invoice(df: pd.DataFrame, text: str) -> dict:
    """Analiza una factura comercial"""
    data = {
        'tipo_documento': 'Factura Comercial',
        'items': [],
        'totales': {}
    }
    
    # Buscar NIT, número de factura, etc.
    nit_match = re.search(r'nit[:\s]*([\d.-]+)', text, re.IGNORECASE)
    if nit_match:
        data['nit'] = nit_match.group(1)
    
    factura_match = re.search(r'(?:factura|no\.?|número)[:\s]*([\w-]+)', text, re.IGNORECASE)
    if factura_match:
        data['numero_factura'] = factura_match.group(1)
    
    # Buscar items (productos/servicios)
    # Intentar extraer de la tabla
    if len(df) > 0:
        for idx, row in df.iterrows():
            item = {}
            for col in df.columns:
                item[col] = row[col]
            data['items'].append(item)
    
    # Buscar totales
    subtotal_match = re.search(r'subtotal[:\s]*\$?\s*([\d.,]+)', text, re.IGNORECASE)
    if subtotal_match:
        data['totales']['subtotal'] = subtotal_match.group(1)
    
    iva_match = re.search(r'iva[:\s]*\$?\s*([\d.,]+)', text, re.IGNORECASE)
    if iva_match:
        data['totales']['iva'] = iva_match.group(1)
    
    total_match = re.search(r'total[:\s]*\$?\s*([\d.,]+)', text, re.IGNORECASE)
    if total_match:
        data['totales']['total'] = total_match.group(1)
    
    return data


def analyze_generic_document(df: pd.DataFrame, text: str) -> dict:
    """Analiza un documento genérico"""
    return {
        'tipo_documento': 'Documento',
        'datos': df.to_dict(orient='records')[:50],  # Primeras 50 filas
        'resumen': {
            'filas_totales': len(df),
            'columnas': list(df.columns)
        }
    }


def smart_analyze(df: pd.DataFrame, text: str = "") -> dict:
    """Analiza el documento y devuelve información estructurada"""
    
    # Combinar texto extraído con DataFrame
    full_text = text + " " + " ".join([" ".join(str(x) for x in row) for _, row in df.iterrows()])
    
    # Detectar tipo de documento
    doc_type = detect_document_type(full_text, df)
    logger.info(f"Tipo detectado: {doc_type}")
    
    # Analizar según el tipo
    if doc_type == 'extracto_bancario':
        return analyze_bank_statement(df, full_text)
    elif doc_type == 'factura_servicios':
        return analyze_utility_bill(df, full_text)
    elif doc_type == 'factura_comercial':
        return analyze_invoice(df, full_text)
    else:
        return analyze_generic_document(df, full_text)


def create_analysis_excel(df_raw: pd.DataFrame, analysis: dict) -> BytesIO:
    """Crea Excel con análisis basado en el tipo de documento"""
    
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        
        # Hoja 1: Resumen
        resumen_data = {'Concepto': [], 'Valor': []}
        
        doc_type = analysis.get('tipo_documento', 'Documento')
        resumen_data['Concepto'].append('Tipo de Documento')
        resumen_data['Valor'].append(doc_type)
        
        if 'resumen' in analysis:
            resumen = analysis['resumen']
            if 'total_ingresos' in resumen:
                resumen_data['Concepto'].append('Total Ingresos')
                resumen_data['Valor'].append(f"${resumen['total_ingresos']:,.0f}")
            if 'total_gastos' in resumen:
                resumen_data['Concepto'].append('Total Gastos')
                resumen_data['Valor'].append(f"${resumen['total_gastos']:,.0f}")
            if 'balance' in resumen:
                resumen_data['Concepto'].append('Balance')
                resumen_data['Valor'].append(f"${resumen['balance']:,.0f}")
            if 'num_transacciones' in resumen:
                resumen_data['Concepto'].append('Número de Transacciones')
                resumen_data['Valor'].append(str(resumen['num_transacciones']))
        
        # Gastos por categoría (si existe)
        if 'gastos_por_categoria' in analysis:
            resumen_data['Concepto'].append('')
            resumen_data['Valor'].append('')
            resumen_data['Concepto'].append('Gastos por Categoría')
            resumen_data['Valor'].append('')
            for cat, valor in analysis['gastos_por_categoria'].items():
                resumen_data['Concepto'].append(f'  {cat}')
                resumen_data['Valor'].append(f"${valor:,.0f}")
        
        # Conceptos de factura (si existe)
        if 'conceptos' in analysis:
            resumen_data['Concepto'].append('')
            resumen_data['Valor'].append('')
            for concepto in analysis['conceptos']:
                resumen_data['Concepto'].append(concepto['nombre'])
                resumen_data['Valor'].append(str(concepto.get('valores', [''])[0]) if concepto.get('valores') else '')
        
        # Totales de factura
        if 'totales' in analysis:
            resumen_data['Concepto'].append('')
            resumen_data['Valor'].append('')
            for key, val in analysis['totales'].items():
                resumen_data['Concepto'].append(key.title())
                resumen_data['Valor'].append(f"${val}" if isinstance(val, str) else val)
        
        df_resumen = pd.DataFrame(resumen_data)
        df_resumen.to_excel(writer, sheet_name='Resumen', index=False)
        
        # Hoja 2: Transacciones/Detalles
        if 'transactions' in analysis and analysis['transactions']:
            df_trans = pd.DataFrame(analysis['transactions'])
            df_trans.to_excel(writer, sheet_name='Transacciones', index=False)
        elif 'items' in analysis and analysis['items']:
            df_items = pd.DataFrame(analysis['items'])
            df_items.to_excel(writer, sheet_name='Items', index=False)
        elif 'datos' in analysis:
            df_datos = pd.DataFrame(analysis['datos'])
            df_datos.to_excel(writer, sheet_name='Datos', index=False)
        
        # Hoja 3: Datos Completos
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
                adjusted_width = min(max_length + 2, 60)
                ws.column_dimensions[column].width = adjusted_width
    
    output.seek(0)
    return output


@app.get("/")
async def root():
    return {
        "message": "PDF to Excel Converter API",
        "version": "3.1.0",
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
            analysis = smart_analyze(df, text)
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