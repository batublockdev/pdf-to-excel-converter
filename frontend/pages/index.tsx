import { useState, useRef } from 'react'
import axios from 'axios'

const API_URL = 'https://pdf-to-excel-converter-production-3bd9.up.railway.app'

export default function Home() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [previewData, setPreviewData] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<'raw' | 'analysis'>('raw')
  const [password, setPassword] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile && selectedFile.type === 'application/pdf') {
      setFile(selectedFile)
      setError(null)
      setPreviewData(null)
    } else {
      setError('Por favor selecciona un archivo PDF válido')
    }
  }

  const handlePreview = async () => {
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)
    if (password) {
      formData.append('password', password)
    }

    try {
      const response = await axios.post(`${API_URL}/api/preview`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setPreviewData(response.data)
    } catch (err: any) {
      console.error('Preview error:', err)
      if (err.response?.data?.detail?.includes('contraseña')) {
        setPreviewData({ encrypted: true })
      } else {
        setError(err.response?.data?.detail || 'Error al previsualizar')
      }
    }
  }

  const handleUpload = async () => {
    if (!file) {
      setError('Por favor selecciona un archivo PDF')
      return
    }

    setUploading(true)
    setProgress(0)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('mode', mode)
    if (password) {
      formData.append('password', password)
    }

    try {
      const response = await axios.post(`${API_URL}/api/convert`, formData, {
        responseType: 'blob',
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1))
          setProgress(percent)
        }
      })

      // Download
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      const filename = mode === 'analysis' 
        ? file.name.replace('.pdf', '_analisis.xlsx')
        : file.name.replace('.pdf', '.xlsx')
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.remove()

      setError(null)
    } catch (err: any) {
      console.error('Error:', err)
      setError(err.response?.data?.detail || 'Error al procesar el PDF')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-blue-50">
      {/* Header */}
      <header>
        <div className="header-content">
          <div className="logo">
            <span className="logo-icon">📊</span>
            <span className="logo-text">PDF a Excel</span>
          </div>
          <span style={{ color: '#6b7280', fontSize: '0.95rem' }}>
            Gratis • Rápido • Seguro
          </span>
        </div>
      </header>

      {/* Main */}
      <main>
        {/* Hero */}
        <div className="hero">
          <h2>Convierte tus PDFs a Excel en Segundos</h2>
          <p>Estados de cuenta, facturas, tablas - todo a Excel limpio automáticamente</p>
        </div>

        {/* Upload Card */}
        <div className="upload-card">
          {/* Drop Zone */}
          <div
            className={`drop-zone ${file ? 'has-file' : ''}`}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <div className="drop-zone-icon">📁</div>
            <h3>{file ? file.name : 'Arrastra tu PDF aquí o haz clic para seleccionar'}</h3>
            <p>Máximo 50MB • Soporta cualquier formato de tabla</p>
          </div>

          {/* Password Input */}
          {(previewData?.encrypted || file) && (
            <div style={{ marginTop: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 500 }}>
                🔐 Contraseña del PDF (si está protegido):
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Dejar vacío si no tiene contraseña"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  borderRadius: '0.5rem',
                  border: '1px solid #e5e7eb',
                  fontSize: '1rem'
                }}
              />
            </div>
          )}

          {/* Mode Selection */}
          {file && (
            <div style={{ marginTop: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.75rem', fontWeight: 600, fontSize: '1.1rem' }}>
                Elige el modo de conversión:
              </label>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <button
                  onClick={() => setMode('raw')}
                  style={{
                    flex: 1,
                    minWidth: '200px',
                    padding: '1rem 1.5rem',
                    borderRadius: '0.75rem',
                    border: mode === 'raw' ? '2px solid #3b82f6' : '2px solid #e5e7eb',
                    background: mode === 'raw' ? '#eff6ff' : 'white',
                    cursor: 'pointer',
                    textAlign: 'left' as const
                  }}
                >
                  <div style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>📊 Modo Raw</div>
                  <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>
                    Excel con todos los datos extraídos tal como están
                  </div>
                </button>
                <button
                  onClick={() => setMode('analysis')}
                  style={{
                    flex: 1,
                    minWidth: '200px',
                    padding: '1rem 1.5rem',
                    borderRadius: '0.75rem',
                    border: mode === 'analysis' ? '2px solid #10b981' : '2px solid #e5e7eb',
                    background: mode === 'analysis' ? '#ecfdf5' : 'white',
                    cursor: 'pointer',
                    textAlign: 'left' as const
                  }}
                >
                  <div style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>💡 Modo Análisis</div>
                  <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>
                    Excel organizado: categorías, gastos, ingresos y resumen
                  </div>
                </button>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="error-message">
              ⚠️ {error}
            </div>
          )}

          {/* Progress */}
          {uploading && (
            <div className="progress-container">
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="progress-text">Procesando... {progress}%</p>
            </div>
          )}

          {/* Preview */}
          {previewData && !previewData.encrypted && !uploading && (
            <div className="preview-card">
              <h4>📋 Vista Previa: {previewData.filename}</h4>
              <p><strong>Total de filas:</strong> {previewData.total_rows}</p>
              <p><strong>Columnas:</strong> {previewData.columns?.slice(0, 5).join(', ')}{previewData.columns?.length > 5 ? '...' : ''}</p>
            </div>
          )}

          {/* Encrypted Warning */}
          {previewData?.encrypted && (
            <div style={{ 
              marginTop: '1rem', 
              padding: '1rem', 
              background: '#fef3c7', 
              borderRadius: '0.5rem',
              color: '#92400e'
            }}>
              🔒 Este PDF está protegido con contraseña. Ingresa la contraseña arriba.
            </div>
          )}

          {/* Convert Button */}
          {file && !uploading && (
            <button 
              className="convert-button" 
              onClick={handleUpload}
              style={{
                background: mode === 'analysis' 
                  ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
                  : 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)'
              }}
            >
              {mode === 'analysis' ? '💡 Analizar y Crear Excel' : '📊 Convertir a Excel'}
            </button>
          )}
        </div>

        {/* Features */}
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon">🔒</div>
            <h3>100% Seguro</h3>
            <p>Tus archivos se procesan en memoria y se eliminan automáticamente. Nadie tiene acceso a tus datos.</p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">⚡</div>
            <h3>Súper Rápido</h3>
            <p>Convierte archivos de hasta 50 páginas en segundos. Sin esperas, sin complicaciones.</p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">💡</div>
            <h3>Análisis Inteligente</h3>
            <p>Modo análisis que categoriza gastos, detecta ingresos y crea resúmenes automáticos.</p>
          </div>
        </div>

        {/* How It Works */}
        <div className="how-it-works">
          <h2>Cómo Funciona</h2>
          <div className="steps-grid">
            <div className="step">
              <div className="step-number">1</div>
              <h3>Sube tu PDF</h3>
              <p>Arrastra o selecciona cualquier PDF con tablas, estados de cuenta o facturas.</p>
            </div>

            <div className="step">
              <div className="step-number">2</div>
              <h3>Elige el modo</h3>
              <p>Raw para datos completos, o Análisis para Excel organizado con categorías.</p>
            </div>

            <div className="step">
              <div className="step-number">3</div>
              <h3>Descarga Excel</h3>
              <p>Obtén un Excel limpio y formateado al instante, listo para usar.</p>
            </div>
          </div>
        </div>

        {/* Supported Formats */}
        <div style={{ maxWidth: '1200px', margin: '0 auto 3rem', padding: '0 1rem' }}>
          <h2 style={{ textAlign: 'center', marginBottom: '1.5rem' }}>PDFs Soportados</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
            {[
              { icon: '🏦', title: 'Estados de Cuenta', desc: 'Bancolombia, Davivienda, BBVA, etc.' },
              { icon: '📄', title: 'Facturas', desc: 'EPM, Claro, servicios públicos' },
              { icon: '📊', title: 'Reportes', desc: 'Cualquier PDF con tablas' },
              { icon: '🔐', title: 'PDFs Protegidos', desc: 'Con contraseña' },
              { icon: '📷', title: 'PDFs Escaneados', desc: 'Usamos OCR para extraer texto' },
            ].map((item, i) => (
              <div key={i} style={{
                padding: '1rem',
                background: 'white',
                borderRadius: '0.75rem',
                border: '1px solid #e5e7eb'
              }}>
                <span style={{ fontSize: '1.5rem' }}>{item.icon}</span>
                <h4 style={{ marginTop: '0.5rem' }}>{item.title}</h4>
                <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>{item.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* FAQ */}
        <div className="faq-section">
          <h2>Preguntas Frecuentes</h2>
          <div className="faq-grid">
            <div className="faq-item">
              <h3>¿Es realmente gratis?</h3>
              <p>Sí, puedes convertir hasta 25 PDFs gratis al mes. Para más volumen hay planes de pago.</p>
            </div>

            <div className="faq-item">
              <h3>¿Qué tipos de PDF acepta?</h3>
              <p>Estados de cuenta, facturas, tablas financieras, PDFs escaneados y protegidos con contraseña.</p>
            </div>

            <div className="faq-item">
              <h3>¿Qué es el Modo Análisis?</h3>
              <p>Organiza automáticamente tus gastos por categorías, detecta ingresos y crea un resumen financiero.</p>
            </div>

            <div className="faq-item">
              <h3>¿Mis datos están seguros?</h3>
              <p>Sí, se procesan en memoria y se eliminan inmediatamente. No guardamos nada.</p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer>
        <p>© 2024 PDF a Excel. Hecho con ❤️ para contadores y negocios.</p>
      </footer>
    </div>
  )
}