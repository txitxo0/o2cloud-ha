# 🔐 Extractor de Credenciales O2 Cloud

## Problema

Las credenciales de O2 Cloud **expiran periódicamente** (cada 2-4 semanas). 

La integración requiere reautenticación manual cada cierto tiempo, pero el proceso es simple:

## Solución

Este script **automatiza completamente** la extracción de credenciales sin intervención manual compleja.

## Instalación

### 1. Instalar dependencias

```bash
pip install playwright
playwright install chromium
```

### 2. Ejecutar el script

```bash
# Windows/Mac/Linux
python extract_o2_credentials.py
```

## Cómo funciona

```
1. Script abre navegador real
2. Tú inicias sesión en O2 Cloud (teléfono + contraseña + SMS)
3. Script espera a que estés autenticado
4. Script extrae automáticamente credenciales
5. Script muestra valores para copiar a HA
```

**Tiempo total: 2-3 minutos**

## Uso

### Primera vez (configuración inicial)

```bash
python extract_o2_credentials.py
# → Copia los valores que muestra
# → Pégalos en Home Assistant (Ajustes > Dispositivos e integraciones)
```

### Reautenticación (cada 2-4 semanas)

Si ves error 401 en HA:

```bash
python extract_o2_credentials.py
# → Copia las credenciales nuevas
# → Ve a Home Assistant
# → Ajustes > Dispositivos e integraciones > O2 Cloud > Reautenticar
# → Pega credenciales nuevas
```

## Ventajas

✅ **Automático**: No necesitas abrir DevTools (F12)
✅ **Seguro**: Credenciales nunca pasan por redes
✅ **Portable**: Funciona en Windows, Mac, Linux
✅ **Rápido**: 2-3 minutos por reauth
✅ **Guardado**: Las credenciales se guardan en `o2_credentials.json`

## Troubleshooting

### "Playwright no instalado"
```bash
pip install playwright
```

### "Timeout esperando sesión"
- Asegúrate de iniciar sesión en el navegador que se abre
- Puede haber CAPTCHA
- O2 puede pedir SMS

### El navegador no se abre
```bash
# Instalar navegadores (primera vez)
playwright install chromium
```

## Archivo generado

Cada vez que ejecutas el script, genera `o2_credentials.json`:

```json
{
  "validation_key": "5f245e42344c2d56235b504e5e454a46",
  "user_agent": "Mozilla/5.0 ...",
  "cookies": {
    "JSESSIONID": "...",
    "validationKey": "...",
    ...
  }
}
```

Puedes usarlo como referencia o compartirlo de forma segura (sin exponer en GitHub).

## Seguridad

⚠️ **IMPORTANTE**:
- Las credenciales se guardan en `o2_credentials.json`
- **No compartas** este archivo en GitHub o público
- Bórralo después de copiar en HA
- Las credenciales están cifradas en HA

## Alternativa manual

Si prefieres extraer credenciales manualmente:

1. Abre https://cloud.o2online.es en navegador
2. F12 → Network → Reload
3. Busca request a `/sapi/`
4. Copia URL (para validationkey)
5. Copia cookies (devtools)
6. Copia user-agent

Pero el script lo hace automáticamente 🤖

---

**Creado para simplificar la gestión de credenciales de O2 Cloud en Home Assistant.**
