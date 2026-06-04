/** @type {import('next').NextConfig} */
const nextConfig = {
  // Habilitar para Vercel
  output: 'standalone',
  // Configuración de imágenes
  images: {
    domains: [],
  },
  // Variables de entorno públicas
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
}

module.exports = nextConfig