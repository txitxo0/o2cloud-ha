# 🧪 Testing Local de O2CloudClient

## Descripción

Script para testear **localmente** (sin Home Assistant) que las credenciales funcionan.

Útil para:
- ✅ Validar credenciales nuevas
- ✅ Debug sin copiar a HA continuamente
- ✅ Ver logs detallados en tiempo real
- ✅ Iterar rápido

## Instalación

### 1. Instalar dependencias

```bash
pip install aiohttp
```

### 2. Preparar credenciales

**Opción A: Archivo JSON** (más fácil)

```bash
# Usa el script helper para extraer
python extract_o2_credentials.py

# Genera o2_credentials.json automáticamente
```

**Opción B: Argumentos de línea de comando**

```bash
python test_o2cloud_local.py \
  --validation-key "5f245e42344c2d56235b504e5e454a46" \
  --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..." \
  --cookies '{"JSESSIONID":"...", "validationKey":"..."}'
```

## Uso

### Con archivo de credenciales (recomendado)

```bash
python test_o2cloud_local.py --credentials o2_credentials.json
```

**Salida esperada:**

```
2026-07-06 14:00:00,123 - __main__ - INFO - ======================================================================
2026-07-06 14:00:00,124 - __main__ - INFO - TESTING O2 CLOUD CLIENT LOCAL
2026-07-06 14:00:00,125 - __main__ - INFO - ======================================================================
2026-07-06 14:00:00,126 - __main__ - INFO - Validation Key: 5f245e42344c2d...
2026-07-06 14:00:00,127 - __main__ - INFO - Cookies: 15 cookies
2026-07-06 14:00:00,128 - __main__ - INFO - User-Agent: Mozilla/5.0 (Windows...
2026-07-06 14:00:00,129 - __main__ - INFO - 
2026-07-06 14:00:00,130 - __main__ - INFO - 📡 Creando cliente O2Cloud...
2026-07-06 14:00:00,131 - __main__ - INFO - ✅ Cliente creado exitosamente
2026-07-06 14:00:00,132 - __main__ - INFO - 
2026-07-06 14:00:00,133 - __main__ - INFO - 🧪 Test 1: test_connection()
2026-07-06 14:00:00,134 - __main__ - INFO - ------
2026-07-06 14:00:00,567 - __main__ - INFO - ✅ Conexión exitosa
2026-07-06 14:00:00,568 - __main__ - INFO - 
2026-07-06 14:00:00,569 - __main__ - INFO - 🧪 Test 2: get_storage_space()
2026-07-06 14:00:00,570 - __main__ - INFO - ------
2026-07-06 14:00:00,890 - __main__ - INFO - ✅ Storage info: {...}
2026-07-06 14:00:00,891 - __main__ - INFO -    Total: 50.00 GB
2026-07-06 14:00:00,892 - __main__ - INFO -    Usado: 23.45 GB
2026-07-06 14:00:00,893 - __main__ - INFO -    Libre: 26.55 GB
2026-07-06 14:00:00,894 - __main__ - INFO -    % utilizado: 46.9%
2026-07-06 14:00:00,895 - __main__ - INFO - 
2026-07-06 14:00:00,896 - __main__ - INFO - 🧪 Test 3: list_folder()
2026-07-06 14:00:00,897 - __main__ - INFO - ------
2026-07-06 14:00:00,923 - __main__ - INFO - ✅ Encontradas 5 carpetas/archivos
2026-07-06 14:00:00,924 - __main__ - INFO -    📁 Documentos
2026-07-06 14:00:00,925 - __main__ - INFO -    📁 Fotos
2026-07-06 14:00:00,926 - __main__ - INFO -    📄 backup_2026.tar
2026-07-06 14:00:00,927 - __main__ - INFO - 
2026-07-06 14:00:00,928 - __main__ - INFO - ======================================================================
2026-07-06 14:00:00,929 - __main__ - INFO - ✅ TODOS LOS TESTS PASARON
2026-07-06 14:00:00,930 - __main__ - INFO - ======================================================================
```

### Con argumentos CLI

```bash
python test_o2cloud_local.py \
  --validation-key "5f245e42344c2d56235b504e5e454a46" \
  --user-agent "Mozilla/5.0 ..." \
  --cookies '{"JSESSIONID":"...", "validationKey":"..."}'
```

## Flujo de trabajo recomendado

### 1. Primera vez (configuración inicial)

```bash
# Paso 1: Extraer credenciales
python extract_o2_credentials.py
# → Genera o2_credentials.json

# Paso 2: Testear localmente
python test_o2cloud_local.py --credentials o2_credentials.json
# → Valida que funcionan

# Paso 3: Si los tests pasan → Copiar a HA
# → Credenciales garantizadas de funcionar
```

### 2. Reautenticación (cada 2-4 semanas)

```bash
# Si ves error 401 en HA:
python extract_o2_credentials.py
# → Nuevas credenciales

python test_o2cloud_local.py --credentials o2_credentials.json
# → Verificar que funcionan

# En HA:
# → Reautenticar con nuevas credenciales
```

## Archivos de salida

Cada ejecución genera:

```
o2cloud_test.log     ← Logs detallados
o2_credentials.json  ← Credenciales (si usaste extract_o2_credentials.py)
```

## Troubleshooting

### "Connection failed: Authentication failed: 401"

Las credenciales **expiraron**. Ejecuta:

```bash
python extract_o2_credentials.py
```

Para extraer credenciales nuevas.

### "ModuleNotFoundError: No module named 'client'"

Asegúrate de estar en el directorio correcto:

```bash
cd C:\dev\sandbox\o2cloud
python test_o2cloud_local.py --credentials o2_credentials.json
```

### "Error parseando cookies JSON"

Las cookies deben ser JSON válido:

```bash
# ❌ MAL
python test_o2cloud_local.py --cookies "JSESSIONID=xxx"

# ✅ BIEN
python test_o2cloud_local.py --cookies '{"JSESSIONID":"xxx"}'
```

## Interpretación de tests

### ✅ Todos pasan
- Credenciales válidas
- Puedes usarlas en HA con confianza
- O2 Cloud responde correctamente

### ❌ test_connection() falla
- Validationkey expirado
- Cookies inválidas
- Problema de conexión a O2

### ❌ get_storage_space() falla
- Error en respuesta de O2
- Problema de permisos
- API puede haber cambiado

### ❌ list_folder() falla
- La carpeta root no existe
- Problema de permisos
- Error en estructura de respuesta

## Ventajas sobre testear en HA

| Aspecto | Local | En HA |
|--------|-------|-------|
| **Iteración** | 30 seg | 5 min (copiar + reiniciar) |
| **Logs** | En consola + archivo | En HA UI |
| **Debug** | Full control | Limitado |
| **Error handling** | Detallado | Vago |
| **Rapidez** | Inmediata | Diferida |

## Ejemplo completo

```bash
# 1. Extraer
python extract_o2_credentials.py
# ← Usuario inicia sesión en navegador

# 2. Testear
python test_o2cloud_local.py --credentials o2_credentials.json
# ← Valida todo funciona

# 3. Si tests OK → Copiar a HA
# → Seguro que funcionará
```

---

**Esto permite iterar 10x más rápido que testear directamente en HA.**
