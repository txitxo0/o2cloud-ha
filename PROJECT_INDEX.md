# 📋 Índice del Proyecto O2 Cloud Backup

## 📁 Estructura completa

```
C:\dev\sandbox\o2cloud\
├── README.md                    ← Documentación principal
├── QUICKSTART.md                ← Guía de inicio rápido (5 min)
├── TECHNICAL.md                 ← Detalles técnicos y arquitectura
├── requirements.txt             ← Dependencias Python
├── .gitignore                   ← Ignorar archivos en Git
├── examples_automations.yaml    ← Ejemplos de automatizaciones
├── test_client_local.py         ← Prueba local del cliente (sin HA)
│
└── custom_components/
    └── o2cloud_backup/          ← La integración de HA
        ├── __init__.py          ← Setup principal, carga platforms y servicios
        ├── manifest.json        ← Metadatos (versión, dependencias, etc)
        ├── const.py             ← Constantes (URLs, timeouts, nombres)
        ├── client.py            ← Cliente HTTP para API O2 Cloud
        ├── coordinator.py       ← Actualizador periódico de cuota
        ├── config_flow.py       ← Flujo de configuración + reauth
        ├── sensor.py            ← Plataforma: sensores (bytes, %)
        ├── binary_sensor.py     ← Plataforma: sensor de sesión (on/off)
        ├── services.py          ← Servicios (upload, prune, test, refresh)
        ├── strings.json         ← Esquemas y UI (inglés)
        └── translations/
            └── es.json          ← Traducciones al español
```

## 🎯 Qué hace cada archivo

| Archivo | Propósito | Desarrollador |
|---------|-----------|---------------|
| `__init__.py` | Punto de entrada, registra servicios y platforms | Principal |
| `manifest.json` | Metadatos para Home Assistant | ✓ Obligatorio |
| `const.py` | URLs de API, timeouts, nombres de config | Configuración |
| `client.py` | Cliente HTTP, endpoints O2 Cloud | Core API |
| `coordinator.py` | Actualización periódica de datos | Core actualización |
| `config_flow.py` | Interfaz de configuración + reauth | UX |
| `sensor.py` | Sensores: total_bytes, used_bytes, free_bytes, used_percent, last_update | Entidades |
| `binary_sensor.py` | Sensor: session_valid | Entidades |
| `services.py` | Servicios: upload_backup, refresh_quota, test_connection | API HA |
| `strings.json` | Esquemas y textos en inglés | Localización |
| `translations/es.json` | Textos en español | Localización |

## 🔑 Flujo de datos

```
[Usuario extrae credenciales del navegador]
            ↓
[config_flow.py valida contra API]
            ↓
[Almacenar en config_entry (seguro)]
            ↓
[O2CloudCoordinator actualiza cada 30 min]
            ↓
[Client.get_storage_space() → parsear respuesta]
            ↓
[Sensores refrescan con nuevos datos]
            ↓
[Dashboard muestra total, usado, libre, %]
            ↓
[Usuario llama service: upload_backup → archivo sube a O2]
```

## 🚀 Primeros pasos

1. **Copiar a HA**:
   ```
   cp -r C:\dev\sandbox\o2cloud\custom_components\o2cloud_backup \
         ~/.homeassistant/custom_components/
   ```

2. **Reiniciar HA**

3. **Ir a Ajustes → Dispositivos e integraciones**

4. **Buscar "O2 Cloud Backup"**

5. **Seguir QUICKSTART.md**

## 📊 Sensores disponibles

```
sensor.o2cloud_total_bytes      [Bytes]      Capacidad total
sensor.o2cloud_used_bytes       [Bytes]      Capacidad usada
sensor.o2cloud_free_bytes       [Bytes]      Capacidad libre
sensor.o2cloud_used_percent     [%]          Porcentaje usado
sensor.o2cloud_last_update      [ISO]        Última actualización
binary_sensor.o2cloud_session_valid [On/Off] Estado sesión
```

## 🔧 Servicios disponibles

```
o2cloud_backup.upload_backup     Subir archivo
o2cloud_backup.refresh_quota     Actualizar cuota manualmente
o2cloud_backup.test_connection   Probar conexión
```

## 🔐 Seguridad

- ✓ Credenciales en storage cifrado (no en logs)
- ✓ Validationkey como secreto
- ✓ Limpieza manual disponible
- ✓ Reauth cuando expire sesión
- ✗ No es API oficial de O2 (es interna)

## 📝 Desarrollo futuro (MVP no incluye)

- [ ] Retención automática (prune_backups)
- [ ] Verificación SHA256 de uploads
- [ ] Sincronización bidireccional
- [ ] Métricas de velocidad
- [ ] Soporte múltiples cuentas
- [ ] Cifrado en reposo

## 🛠️ Stack técnico

- **Python**: 3.11+
- **Framework**: Home Assistant 2024.12+
- **HTTP**: aiohttp
- **Validación**: voluptuous
- **API**: REST interna O2 Cloud

## 📞 Contacto

Para problemas:
1. Revisar logs en HA (Herramientas desarrollo → Logs)
2. Buscar en TECHNICAL.md si es limitación conocida
3. Validar credenciales en QUICKSTART.md

---

**Estado**: MVP funcional para backups simples. Apto para uso personal en producción con reautenticación periódica.
