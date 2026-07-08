# DevContainer para O2 Cloud Backup

Este devcontainer proporciona un entorno Python completo preconfigurado para testear la integración O2 Cloud sin necesidad de Home Assistant.

## Qué incluye

✅ **Python 3.11** - Versión recomendada
✅ **Dependencias instaladas** - aiohttp, playwright, voluptuous, pytest
✅ **VS Code Extensions** - Python, Pylance, Debugger
✅ **Git** - Para control de versiones
✅ **Port forwarding** - Puerto 8123 para HA (si lo necesitas)

## Cómo usar

### 1. Abrir en DevContainer

**Opción A: VS Code (recomendado)**
```
1. Abre la carpeta en VS Code
2. Presiona: Ctrl+Shift+P (Cmd+Shift+P en Mac)
3. Busca: "Dev Containers: Reopen in Container"
4. Selecciona
5. Espera a que se configure (primera vez: 2-3 min)
```

**Opción B: GitHub Codespaces**
```
1. En GitHub: Haz click en "Code" → "Codespaces"
2. Crea nuevo Codespace
3. Abre en el navegador o VS Code
```

### 2. Terminal dentro del DevContainer

Una vez dentro, abre una terminal:

```bash
# Verificar Python
python --version
# → Python 3.11.x

# Verificar dependencias
pip list | grep -E "aiohttp|playwright|pytest"
```

### 3. Ejecutar scripts de testing

```bash
# Extraer credenciales
python extract_o2_credentials.py

# Testear credenciales localmente
python test_o2cloud_local.py --credentials o2_credentials.json

# Ejecutar tests
pytest tests/
```

## Flujo de trabajo típico

```bash
# 1. Terminal abierta en devcontainer

# 2. Extraer credenciales frescas
python extract_o2_credentials.py
# → Abre navegador en tu PC (no en el container)
# → Inicia sesión en O2 Cloud
# → Script genera o2_credentials.json

# 3. Testear localmente
python test_o2cloud_local.py --credentials o2_credentials.json
# → Valida conexión, storage, carpetas
# → Si ✅ → Credenciales OK para usar en HA

# 4. Ver logs en tiempo real
tail -f o2cloud_test.log
```

## Ventajas del DevContainer

| Aspecto | Local | DevContainer |
|--------|-------|--------------|
| Setup | Manual, propenso a errores | Automático |
| Reproducibilidad | Depende del sistema | Igual en todos lados |
| Aislamiento | Ensucia el sistema | Entorno limpio |
| Colaboración | Difícil sincronizar env | Fácil: solo copiar container |
| Python | Puede estar desactualizado | 3.11 garantizado |

## Estructura del devcontainer

```
.devcontainer/
├── devcontainer.json      ← Configuración principal
└── README.md              ← Este archivo

Archivos en raíz que se usan:
├── requirements.txt       ← Dependencias (install automático)
├── extract_o2_credentials.py
├── test_o2cloud_local.py
└── custom_components/o2cloud/
    └── client.py          ← Código a testear
```

## Comandos útiles

### Dentro del DevContainer

```bash
# Instalar más paquetes si es necesario
pip install <paquete>

# Ver logs en tiempo real
tail -f o2cloud_test.log

# Ejecutar test específico
pytest tests/test_client.py -v

# Limpiar logs
rm o2cloud_test.log

# Reinstalar dependencias
pip install -r requirements.txt --force-reinstall
```

### Desde VS Code

- **Ctrl+J** - Abrir/cerrar terminal
- **F5** - Debug (si configuras launch.json)
- **Ctrl+Shift+D** - Debug view

## Troubleshooting

### "Cannot connect to Docker daemon"

El devcontainer requiere Docker. Instala:
- **Windows/Mac**: [Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Linux**: `sudo apt install docker.io`

### "Permission denied while trying to connect to Docker daemon"

En Linux:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### "Cannot open display" al ejecutar extract_o2_credentials.py

En Linux con X11:
```bash
# El container necesita acceso a X11
# Esto se maneja automáticamente en la mayoría de casos
# Si aún falla, usa --headless de Playwright
```

### Playwright no funciona

```bash
# Reinstalar navegadores
playwright install chromium
```

## Acceso a archivos

Los archivos en tu PC están disponibles dentro del container:
```bash
# Dentro del container
ls /workspace
# → Ver todos tus archivos
```

Los cambios que hagas se sincronizan automáticamente.

## VS Code Extensions en el Container

El devcontainer instala automáticamente:
- **Python** - Intellisense, linting, debugging
- **Pylance** - Type hints y análisis estático
- **Debugpy** - Debugger integrado
- **Pyright** - Type checker avanzado

Puedes instalar más:
```
Extensiones → Buscar → Install in Container
```

## Salir del DevContainer

```bash
# Opción 1: En VS Code
Ctrl+Shift+P → "Dev Containers: Reopen in Local"

# Opción 2: Cerrar la ventana y volver a abrir sin container
```

## Comandos de limpieza

```bash
# Limpiar container (desde tu PC)
docker system prune -a

# Reconstruir desde cero
Ctrl+Shift+P → "Dev Containers: Rebuild Container"
```

## Para colaboradores

Si compartes tu repo:

```bash
# Los colaboradores solo necesitan:
1. Clonar repo
2. Abrir en VS Code
3. "Dev Containers: Reopen in Container"
4. Listo - mismo entorno que tú

# Sin tener que instalar Python, pip, dependencias manualmente
```

---

**El DevContainer hace que cualquiera pueda testear sin problemas de entorno.**

Para preguntas: Ver README.md en raíz
