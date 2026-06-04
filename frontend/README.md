# PDF to Excel Converter - Frontend

Frontend Next.js para convertir PDFs a Excel.

## Instalación

```bash
npm install
# o
pnpm install
```

## Desarrollo

```bash
npm run dev
```

Abre [http://localhost:3000](http://localhost:3000)

## Variables de Entorno

Crear archivo `.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Deploy en Vercel

1. Conectar repositorio en Vercel
2. Configurar variable de entorno: `NEXT_PUBLIC_API_URL` (URL del backend en Railway)
3. Deploy automático

## Estructura

- `/pages/index.tsx` - Página principal
- `/styles/globals.css` - Estilos globales
- `tailwind.config.js` - Configuración de Tailwind

## Tecnologías

- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- Ant Design