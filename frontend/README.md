# Deploy Instructions for Vercel

## Backend Status
✅ Backend deployed at: https://pdf-to-excel-converter-production-3bd9.up.railway.app

## Frontend Deploy Steps

### Option 1: Via Vercel Dashboard (Recommended)

1. Go to https://vercel.com/new
2. Select "Import Git Repository"
3. Choose: `batublockdev/pdf-to-excel-converter`
4. Configure:
   - Framework Preset: Next.js
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `.next`
5. Add Environment Variable:
   - Name: `NEXT_PUBLIC_API_URL`
   - Value: `https://pdf-to-excel-converter-production-3bd9.up.railway.app`
6. Click "Deploy"

### Option 2: Via Vercel CLI

```bash
cd frontend
vercel login
vercel --prod
```

When prompted:
- Set root directory to `frontend`
- Add environment variable `NEXT_PUBLIC_API_URL`

## After Deploy

Test with a PDF file to ensure:
1. Upload works
2. PDF is processed
3. Excel downloads

## Current Status

- [x] Backend deployed (Railway)
- [ ] Frontend deployed (Vercel)
- [ ] End-to-end testing