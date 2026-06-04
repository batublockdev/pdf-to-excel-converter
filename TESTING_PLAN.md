# Testing Plan - PDF to Excel Converter

## Objetivo
Validar que el producto funciona correctamente y tomar decisiones basadas en datos.

## Fases de Testing

### Fase 1: Backend Health Check
- [ ] Verificar versión del backend
- [ ] Verificar endpoint de salud
- [ ] Verificar CORS

### Fase 2: Testing con PDFs Conocidos
- [ ] Test 1: PDF con tablas (factura EPM)
- [ ] Test 2: PDF sin tablas (xnunx)
- [ ] Test 3: PDF vacío/corrupto
- [ ] Test 4: Archivo no-PDF

### Fase 3: Testing de Edge Cases
- [ ] PDF con muchas páginas
- [ ] PDF con tablas complejas
- [ ] PDF con texto sin tablas
- [ ] PDF protegido con contraseña

### Fase 4: Testing de Performance
- [ ] Tiempo de respuesta
- [ ] Tamaño máximo de archivo
- [ ] Concurrencia

### Fase 5: Frontend Testing
- [ ] UI carga correctamente
- [ ] Upload funciona
- [ ] Preview funciona
- [ ] Download funciona
- [ ] Errores se muestran correctamente

## Resultados y Decisiones

### Métricas de Éxito
- Tiempo de conversión < 5 segundos
- Tasa de éxito > 80% en PDFs con tablas
- Errores claros y útiles

### Decisiones Basadas en Resultados
- Si pasa todos los tests → READY FOR PRODUCTION
- Si falla en PDFs comunes → FIX BEFORE LAUNCH
- Si funciona pero lento → OPTIMIZE

---

## Log de Tests

### [Fecha] - Test ejecutado
- **Input:** [descripción]
- **Output:** [resultado]
- **Decisión:** [acción tomada]