import { useState, useRef } from 'react'
import axios from 'axios'

const API_URL = 'https://pdf-to-excel-converter-production-3bd9.up.railway.app'

export default function Home() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [previewData, setPreviewData] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
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

    try {
      // Preview
      const previewResponse = await axios.post(`${API_URL}/api/preview`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1))
          setProgress(percent)
        }
      })

      setPreviewData(previewResponse.data)

      // Convert
      const convertResponse = await axios.post(`${API_URL}/api/convert`, formData, {
        responseType: 'blob',
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1))
          setProgress(percent)
        }
      })

      // Download
      const url = window.URL.createObjectURL(new Blob([convertResponse.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', file.name.replace('.pdf', '.xlsx'))
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
          {previewData && !uploading && (
            <div className="preview-card">
              <h4>📋 Vista Previa: {previewData.filename}</h4>
              <p><strong>Total de filas:</strong> {previewData.total_rows}</p>
              <p><strong>Tipo detectado:</strong> {previewData.is_bank_statement ? 'Estado de cuenta bancario' : 'Documento con tablas'}</p>
              <p><strong>Columnas:</strong> {previewData.columns?.join(', ')}</p>
            </div>
          )}

          {/* Convert Button */}
          {file && !uploading && (
            <button className="convert-button" onClick={handleUpload}>
              📊 Convertir a Excel
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
            <div className="feature-icon">🌍</div>
            <h3>Multi-idioma</h3>
            <p>Soporta español, inglés, portugués, francés y más. Funciona con bancos de todo el mundo.</p>
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
              <h3>Procesamos</h3>
              <p>Nuestra IA detecta y extrae las tablas automáticamente con precisión.</p>
            </div>

            <div className="step">
              <div className="step-number">3</div>
              <h3>Descarga Excel</h3>
              <p>Obtén un Excel limpio y formateado al instante, listo para usar.</p>
            </div>
          </div>
        </div>

        {/* FAQ */}
        <div className="faq-section">
          <h2>Preguntas Frecuentes</h2>
          <div className="faq-grid">
            <div className="faq-item">
              <h3>¿Es realmente gratis?</h3>
              <p>Sí, durante la fase beta puedes convertir hasta 50 PDFs gratis. Después habrá planes gratuitos y de pago.</p>
            </div>

            <div className="faq-item">
              <h3>¿Qué tipos de PDF acepta?</h3>
              <p>Estados de cuenta bancarios, facturas, tablas financieras, reportes - cualquier PDF con datos tabulares.</p>
            </div>

            <div className="faq-item">
              <h3>¿Dónde se guardan mis archivos?</h3>
              <p>No se guardan en ningún lado. Se procesan en memoria y se eliminan inmediatamente después de la conversión.</p>
            </div>

            <div className="faq-item">
              <h3>¿Funciona con bancos latinoamericanos?</h3>
              <p>Sí, soportamos Bancolombia, BBVA, Davivienda, Banorte, Santander, y más de 3000 bancos mundialmente.</p>
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