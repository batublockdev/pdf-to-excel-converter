import { useState, useRef } from 'react'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <span className="text-3xl mr-3">📊</span>
              <h1 className="text-xl font-bold">PDF a Excel</h1>
            </div>
            <span className="text-gray-500 text-sm">
              Gratis • Rápido • Seguro
            </span>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-4xl mx-auto px-4 py-12 sm:px-6 lg:px-8">
        <div className="text-center mb-8">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Convierte tus PDFs a Excel en Segundos
          </h2>
          <p className="text-xl text-gray-600">
            Estados de cuenta, facturas, tablas - todo a Excel limpio automáticamente
          </p>
        </div>

        {/* Upload Card */}
        <div className="bg-white rounded-xl shadow-md p-8 mb-8">
          {/* Drop Zone */}
          <div
            className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-blue-500 transition-colors cursor-pointer"
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              className="hidden"
            />
            <div className="text-5xl mb-3">📁</div>
            <h3 className="text-lg font-medium mb-2">
              {file ? file.name : 'Arrastra tu PDF aquí o haz clic'}
            </h3>
            <p className="text-gray-500 text-sm">
              Máximo 50MB • Soporta cualquier formato de tabla
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-lg">
              {error}
            </div>
          )}

          {/* Progress */}
          {uploading && (
            <div className="mt-4">
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-center text-sm text-gray-600 mt-2">
                Procesando... {progress}%
              </p>
            </div>
          )}

          {/* Preview */}
          {previewData && !uploading && (
            <div className="mt-6 p-4 bg-gray-50 rounded-lg">
              <h4 className="font-medium mb-2">
                Vista Previa: {previewData.filename}
              </h4>
              <div className="text-sm space-y-1">
                <p><strong>Total de filas:</strong> {previewData.total_rows}</p>
                <p><strong>Tipo detectado:</strong> {previewData.is_bank_statement ? 'Estado de cuenta bancario' : 'Documento con tablas'}</p>
                <p><strong>Columnas:</strong> {previewData.columns?.join(', ')}</p>
              </div>
            </div>
          )}

          {/* Convert Button */}
          {file && !uploading && (
            <button
              onClick={handleUpload}
              className="mt-4 w-full bg-blue-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              📊 Convertir a Excel
            </button>
          )}
        </div>

        {/* Features */}
        <div className="grid md:grid-cols-3 gap-6 mt-12">
          <div className="bg-white p-6 rounded-lg shadow-sm text-center">
            <div className="text-4xl mb-3">🔒</div>
            <h3 className="font-bold mb-2">100% Seguro</h3>
            <p className="text-gray-600 text-sm">
              Tus archivos se procesan en memoria y se eliminan automáticamente
            </p>
          </div>

          <div className="bg-white p-6 rounded-lg shadow-sm text-center">
            <div className="text-4xl mb-3">⚡</div>
            <h3 className="font-bold mb-2">Súper Rápido</h3>
            <p className="text-gray-600 text-sm">
              Convierte archivos de hasta 50 páginas en segundos
            </p>
          </div>

          <div className="bg-white p-6 rounded-lg shadow-sm text-center">
            <div className="text-4xl mb-3">🌍</div>
            <h3 className="font-bold mb-2">Multi-idioma</h3>
            <p className="text-gray-600 text-sm">
              Soporta español, inglés, portugués, francés y más
            </p>
          </div>
        </div>

        {/* How it works */}
        <div className="mt-16">
          <h2 className="text-2xl font-bold text-center mb-8">
            Cómo Funciona
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="bg-blue-100 text-blue-600 rounded-full w-12 h-12 flex items-center justify-center mx-auto mb-4 text-xl font-bold">
                1
              </div>
              <h3 className="font-bold mb-2">Sube tu PDF</h3>
              <p className="text-gray-600 text-sm">
                Arrastra o selecciona cualquier PDF con tablas
              </p>
            </div>

            <div className="text-center">
              <div className="bg-blue-100 text-blue-600 rounded-full w-12 h-12 flex items-center justify-center mx-auto mb-4 text-xl font-bold">
                2
              </div>
              <h3 className="font-bold mb-2">Procesamos</h3>
              <p className="text-gray-600 text-sm">
                Nuestra IA detecta y extrae las tablas automáticamente
              </p>
            </div>

            <div className="text-center">
              <div className="bg-blue-100 text-blue-600 rounded-full w-12 h-12 flex items-center justify-center mx-auto mb-4 text-xl font-bold">
                3
              </div>
              <h3 className="font-bold mb-2">Descarga Excel</h3>
              <p className="text-gray-600 text-sm">
                Obtén un Excel limpio y formateado al instante
              </p>
            </div>
          </div>
        </div>

        {/* FAQ */}
        <div className="mt-16">
          <h2 className="text-2xl font-bold text-center mb-8">
            Preguntas Frecuentes
          </h2>
          <div className="space-y-4">
            <div className="bg-white p-6 rounded-lg shadow-sm">
              <h3 className="font-bold mb-2">¿Es realmente gratis?</h3>
              <p className="text-gray-600">
                Sí, durante la fase beta puedes convertir hasta 50 PDFs gratis. Después habrá planes gratuitos y de pago.
              </p>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-sm">
              <h3 className="font-bold mb-2">¿Qué tipos de PDF acepta?</h3>
              <p className="text-gray-600">
                Estados de cuenta bancarios, facturas, tablas financieras, reportes - cualquier PDF con datos tabulares.
              </p>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-sm">
              <h3 className="font-bold mb-2">¿Dónde se guardan mis archivos?</h3>
              <p className="text-gray-600">
                No se guardan en ningún lado. Se procesan en memoria y se eliminan inmediatamente después de la conversión.
              </p>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-sm">
              <h3 className="font-bold mb-2">¿Funciona con bancos latinoamericanos?</h3>
              <p className="text-gray-600">
                Sí, soportamos Bancolombia, BBVA, Davivienda, Banorte, Santander, y más de 3000 bancos mundialmente.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-100 mt-16 py-8">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-gray-600 text-sm">
            © 2024 PDF a Excel. Hecho con ❤️ para contadores y negocios.
          </p>
        </div>
      </footer>
    </div>
  )
}