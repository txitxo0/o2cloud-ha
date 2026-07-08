# ⚡ Quick Start - O2 Cloud Backup

## 🚀 Empezar en 2 minutos

### Requisito
- **VS Code** instalado
- **Docker** instalado

### Paso 1: Abrir en DevContainer

```
1. Abre esta carpeta en VS Code
2. Presiona: Ctrl+Shift+P
3. Escribe: "Reopen in Container"
4. Selecciona
5. Espera 2-3 minutos (primera vez es más lenta)
```

### Paso 2: Terminal en DevContainer

```
Ctrl+J  ← Abre terminal
```

### Paso 3: Ejecutar scripts

```bash
# Extraer credenciales frescas
python extract_o2_credentials.py
# → Usuario: inicia sesión en navegador
# → Script: extrae automáticamente

# Testear credenciales localmente
python test_o2cloud_local.py --credentials o2_credentials.json
# → Muestra logs detallados
# → Si ✅ TESTS PASARON → listo para HA
```

---

## 📋 Scripts disponibles

| Script | Qué hace | Comando |
|--------|----------|---------|
| **extract_o2_credentials.py** | Extrae credenciales frescas | `python extract_o2_credentials.py` |
| **test_o2cloud_local.py** | Valida credenciales sin HA | `python test_o2cloud_local.py --credentials o2_credentials.json` |
| **test_o2cloud_local.py** | Valida con argumentos CLI | `python test_o2cloud_local.py --validation-key "..." --user-agent "..." --cookies "{...}"` |

---

## 🧪 Workflow completo

```bash
# 1. Extract
python extract_o2_credentials.py
# → Abre navegador en tu PC
# → Tú: inicia sesión
# → Script: genera o2_credentials.json

# 2. Test
python test_o2cloud_local.py --credentials o2_credentials.json
# → Prueba conexión
# → Si ✅ todo bien

# 3. Debug (opcional)
tail -f o2cloud_test.log
# → Ver logs en tiempo real
```

---

## 🔧 Debugging en VS Code

```
F5 → Ejecuta "Test O2Cloud Local"
    (Debug mode con breakpoints)
```

O selecciona en el dropdown superior:
- "Test O2Cloud Local"
- "Extract Credentials"
- "Python: Current File"

---

## 📚 Documentación completa

- [DevContainer README](.devcontainer/README.md)
- [Testing Local](TESTING_LOCAL.md)
- [Credentials Helper](CREDENTIALS_HELPER.md)
- [README](README.md)

---

## ⚠️ Importante

**NUNCA commitear:**
- `o2_credentials.json` ← Credenciales sensibles
- `*.log` ← Contienen datos
- `.env` ← Configuración privada

(Ya está en `.gitignore`)

---

## 🆘 Si algo falla

### Docker no se conecta
```bash
# Windows/Mac: Asegurate que Docker Desktop está corriendo

# Linux:
sudo usermod -aG docker $USER
newgrp docker
```

### "Cannot open display" (Linux con Playwright)
```bash
# El navegador de Playwright debería funcionar
# Si falla, es porque faltan librerías de X11
# Instala dentro del container:
apt-get update && apt-get install -y xvfb
```

### Playwright no inicia
```bash
# Reinstalar navegadores
playwright install chromium
```

---

## 🎯 Próximos pasos después de testing

Una vez que `test_o2cloud_local.py` muestre ✅ **TESTS OK**:

1. Copia `custom_components/o2cloud` a Home Assistant
2. Reinicia HA
3. Configura integración con las credenciales validadas
4. Disfruta del backup en O2 Cloud 🎉

---

**¡Listo! Empieza por `python extract_o2_credentials.py`**
