import { useState, useCallback } from 'react'
import axios from 'axios'
import { Upload, message, Progress, Card, Typography, Space, Button } from 'antd'
import { InboxOutlined, FileExcelOutlined, CloudUploadOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'

const { Title, Paragraph, Text } = Typography
const { Dragger } = Upload

// API URL desde env
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function Home() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [previewData, setPreviewData] = useState<any>(null)

  // Manejar upload
  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('Por favor selecciona un archivo PDF')
      return
    }

    const formData = new FormData()
    fileList.forEach(file => {
      formData.append('file', file.originFileObj as File)
    })

    setUploading(true)
    setProgress(0)

    try {
      // Primero preview
      const previewResponse = await axios.post(`${API_URL}/api/preview`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1))
          setProgress(percent)
        }
      })

      setPreviewData(previewResponse.data)

      // Luego convertir
      const convertResponse = await axios.post(`${API_URL}/api/convert`, formData, {
        responseType: 'blob',
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1))
          setProgress(percent)
        }
      })

      // Descargar archivo
      const url = window.URL.createObjectURL(new Blob([convertResponse.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', fileList[0].name.replace('.pdf', '.xlsx'))
      document.body.appendChild(link)
      link.click()
      link.remove()

      message.success('¡PDF convertido exitosamente!')

    } catch (error: any) {
      console.error('Error:', error)
      message.error(error.response?.data?.detail || 'Error al procesar el PDF')
    } finally {
      setUploading(false)
    }
  }

  // Props del Dragger
  const uploadProps = {
    name: 'file',
    multiple: false,
    accept: '.pdf',
    fileList,
    beforeUpload: (file: File) => {
      const isPdf = file.type === 'application/pdf' || file.name.endsWith('.pdf')
      if (!isPdf) {
        message.error('Solo se aceptan archivos PDF')
        return false
      }
      const isLt50M = file.size / 1024 / 1024 < 50
      if (!isLt50M) {
        message.error('El archivo debe ser menor a 50MB')
        return false
      }
      return false
    },
    onChange: (info: any) => {
      setFileList(info.fileList)
    },
    onDrop: (e: any) => {
      console.log('Dropped files', e.dataTransfer.files)
    },
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <FileExcelOutlined className="text-3xl text-blue-600 mr-3" />
              <Title level={3} className="m-0">
                PDF a Excel
              </Title>
            </div>
            <Text type="secondary">
              Gratis • Rápido • Seguro
            </Text>
          </div>
        </div>
      </header>

      {/* Hero */}
      <main className="max-w-4xl mx-auto px-4 py-12 sm:px-6 lg:px-8">
        <div className="text-center mb-8">
          <Title level={1} className="text-4xl font-bold text-gray-900 mb-4">
            Convierte tus PDFs a Excel en Segundos
          </Title>
          <Paragraph className="text-xl text-gray-600">
            Estados de cuenta, facturas, tablas - todo a Excel limpio automáticamente
          </Paragraph>
        </div>

        {/* Upload Area */}
        <Card className="mb-8">
          <Dragger {...uploadProps} className="upload-dragger">
            <p className="ant-upload-drag-icon">
              <CloudUploadOutlined className="text-5xl text-blue-500" />
            </p>
            <Title level={4} className="mb-2">
              Arrastra tu PDF aquí
            </Title>
            <Paragraph className="text-gray-500">
              o haz clic para seleccionar
            </Paragraph>
            <Text type="secondary">
              Máximo 50MB • Soporta cualquier formato de tabla
            </Text>
          </Dragger>

          {/* Progress */}
          {uploading && (
            <div className="mt-4">
              <Progress percent={progress} status="active" />
              <Text className="text-center block mt-2">
                Procesando...
              </Text>
            </div>
          )}

          {/* Preview */}
          {previewData && !uploading && (
            <div className="mt-6 p-4 bg-gray-50 rounded">
              <Title level={5} className="mb-2">
                Vista Previa: {previewData.filename}
              </Title>
              <Space direction="vertical" className="w-full">
                <Text>
                  <strong>Total de filas:</strong> {previewData.total_rows}
                </Text>
                <Text>
                  <strong>Tipo detectado:</strong> {previewData.is_bank_statement ? 'Estado de cuenta bancario' : 'Documento con tablas'}
                </Text>
                <Text>
                  <strong>Columnas:</strong> {previewData.columns.join(', ')}
                </Text>
              </Space>
            </div>
          )}

          {/* Convert Button */}
          {fileList.length > 0 && !uploading && (
            <Button
              type="primary"
              size="large"
              icon={<FileExcelOutlined />}
              onClick={handleUpload}
              className="mt-4 w-full"
            >
              Convertir a Excel
            </Button>
          )}
        </Card>

        {/* Features */}
        <div className="grid md:grid-cols-3 gap-6 mt-12">
          <Card className="text-center">
            <div className="text-4xl mb-3">🔒</div>
            <Title level={4} className="mb-2">100% Seguro</Title>
            <Text type="secondary">
              Tus archivos se procesan en memoria y se eliminan automáticamente
            </Text>
          </Card>

          <Card className="text-center">
            <div className="text-4xl mb-3">⚡</div>
            <Title level={4} className="mb-2">Súper Rápido</Title>
            <Text type="secondary">
              Convierte archivos de hasta 50 páginas en segundos
            </Text>
          </Card>

          <Card className="text-center">
            <div className="text-4xl mb-3">🌍</div>
            <Title level={4} className="mb-2">Multi-idioma</Title>
            <Text type="secondary">
              Soporta español, inglés, portugués, francés y más
            </Text>
          </Card>
        </div>

        {/* How it works */}
        <div className="mt-16">
          <Title level={2} className="text-center mb-8">
            Cómo Funciona
          </Title>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="bg-blue-100 text-blue-600 rounded-full w-12 h-12 flex items-center justify-center mx-auto mb-4 text-xl font-bold">
                1
              </div>
              <Title level={4} className="mb-2">Sube tu PDF</Title>
              <Text type="secondary">
                Arrastra o selecciona cualquier PDF con tablas
              </Text>
            </div>

            <div className="text-center">
              <div className="bg-blue-100 text-blue-600 rounded-full w-12 h-12 flex items-center justify-center mx-auto mb-4 text-xl font-bold">
                2
              </div>
              <Title level={4} className="mb-2">Procesamos</Title>
              <Text type="secondary">
                Nuestra IA detecta y extrae las tablas automáticamente
              </Text>
            </div>

            <div className="text-center">
              <div className="bg-blue-100 text-blue-600 rounded-full w-12 h-12 flex items-center justify-center mx-auto mb-4 text-xl font-bold">
                3
              </div>
              <Title level={4} className="mb-2">Descarga Excel</Title>
              <Text type="secondary">
                Obtén un Excel limpio y formateado al instante
              </Text>
            </div>
          </div>
        </div>

        {/* FAQ */}
        <div className="mt-16">
          <Title level={2} className="text-center mb-8">
            Preguntas Frecuentes
          </Title>
          <Space direction="vertical" className="w-full">
            <Card>
              <Title level={5}>¿Es realmente gratis?</Title>
              <Text>
                Sí, durante la fase beta puedes convertir hasta 50 PDFs gratis. Después habrá planes gratuitos y de pago.
              </Text>
            </Card>

            <Card>
              <Title level={5}>¿Qué tipos de PDF acepta?</Title>
              <Text>
                Estados de cuenta bancarios, facturas, tablas financieras, reportes - cualquier PDF con datos tabulares.
              </Text>
            </Card>

            <Card>
              <Title level={5}>¿Dónde se guardan mis archivos?</Title>
              <Text>
                No se guardan en ningún lado. Se procesan en memoria y se eliminan inmediatamente después de la conversión.
              </Text>
            </Card>

            <Card>
              <Title level={5}>¿Funciona con bancos latinoamericanos?</Title>
              <Text>
                Sí, soportamos Bancolombia, BBVA, Davivienda, Banorte, Santander, y más de 3000 bancos mundialmente.
              </Text>
            </Card>
          </Space>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-100 mt-16 py-8">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <Text type="secondary">
            © 2024 PDF a Excel. Hecho con ❤️ para contadores y negocios.
          </Text>
        </div>
      </footer>

      <style jsx global>{`
        .upload-dragger:hover {
          border-color: #3b82f6;
        }
      `}</style>
    </div>
  )
}