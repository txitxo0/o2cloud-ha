# Notas técnicas y arquitectura

## Estructura de la integración

```
custom_components/o2cloud_backup/
├── __init__.py              # Setup, carga platforms, servicios
├── manifest.json            # Metadatos y dependencias
├── const.py                 # Constantes (URLs, timeouts, etc)
├── client.py                # Cliente HTTP para API O2 Cloud
├── coordinator.py           # Actualizador periódico de datos
├── config_flow.py           # Flujo de configuración (alta + reauth)
├── sensor.py                # Plataforma: sensores numéricos
├── binary_sensor.py         # Plataforma: sensores on/off
├── services.py              # Definición de servicios
├── strings.json             # Esquemas y textos en inglés
└── translations/
    └── es.json              # Textos en español
```

## Flujo de autenticación

1. **Primera configuración**: usuario ejecuta config_flow
2. **Extrae credenciales**: validationkey, user_agent, cookies (opcionales)
3. **Validación**: llama `client.test_connection()` contra API
4. **Almacenamiento**: guarda credenciales en storage seguro de HA
5. **Coordinador**: actualiza cuota cada 15-60 min según config
6. **Expiracion**: si API devuelve 401/403, marca session_valid=false
7. **Reautenticación**: interfaz guía al usuario a reconfigurar

## API de O2 Cloud (interna)

### Base URL
```
https://cloud.o2online.es/sapi/
https://upload.cloud.o2online.es/sapi/upload
```

### Parámetro obligatorio
Todas las requests llevan `?validationkey=VALUE` en query string.

### Headers críticos
- `User-Agent`: se extrae del navegador y se reutiliza
- `Cookie`: cookies de sesión (opcional, pero recomendado)

### Endpoints

#### Obtener cuota
```
GET /media?action=get-storage-space&softdeleted=true|false&validationkey=...
Respuesta: {"quota": 1099511627776, "used": 134217728}
```

#### Listar carpeta
```
GET /media/folder?action=list&parentid=<id>&limit=200&validationkey=...
Respuesta: {"folders": [...], "files": [...]}
```

#### Crear carpeta
```
POST /media/folder?action=save&validationkey=...
Body: {"parentid": "...", "name": "backup"}
Respuesta: {"folderid": "...", "name": "backup"}
```

#### Iniciar subida
```
POST /upload?action=init&validationkey=...
Respuesta: {"uploadid": "..."}
```

#### Subir archivo
```
POST /upload?uploadid=<id>&folderid=<id>&validationkey=...
Body: multipart/form-data con archivo
Respuesta: {"timestamp": "..."}
```

#### Eliminar archivo
```
POST /media/file?action=delete&softdelete=true|false&validationkey=...
Body: {"fileid": "..."}
Respuesta: {}
```

## Seguridad

### Credenciales
- Se guardan en `config_entry.data` (storage cifrado de HA)
- No se escriben en logs (campos "password")
- Se pueden limpiar desde UI

### Cookies
- Se envían en cada request para mantener sesión
- User-Agent debe coincidir con el del navegador original
- Si cambian, la sesión se invalida (401/403)

### Reintentos
- Backoff exponencial en uploads (3 intentos)
- Timeout por defecto: 30s para requests, 300s para uploads
- No reintentar en 401/403 (credenciales invalidas)

## Mantenimiento a largo plazo

### Si la API de O2 cambia
1. Endpoint se mueve → actualizar `const.py`
2. Parámetros cambian → actualizar `client.py`
3. Autenticación cambia → revisar `config_flow.py`
4. Estructura respuesta → ajustar parseo en `coordinator.py`

### Testing recomendado
1. Prueba `test_connection` regularmente (cron semanal)
2. Verifica sensores actualizan (logs, histórico)
3. Sube archivo pequeño mensualmente (verificar integridad)
4. Limpia backups antiguos regularmente

### Monitoreo
- Configurar alerta si `session_valid=false`
- Alerta si cuota > 80%
- Log de cada upload/delete exitoso
- Dashboard con sensores actualizados

## Limitaciones conocidas

1. **API interna**: puede cambiar sin aviso
2. **No oficial**: no hay SLA ni soporte de O2
3. **Autenticación débil**: validationkey no tiene expiration time oficial
4. **Sin OAuth**: requiere extracción manual de credenciales
5. **User-Agent crítico**: si cambia navegador/versión, puede fallar

## Roadmap futuro (no MVP)

- [ ] Sincronización bidireccional (download backups)
- [ ] Gestión de carpetas desde HA
- [ ] Política de retención automática (prune service)
- [ ] Cálculo de hash para verificación de integridad
- [ ] Soporte para múltiples cuentas O2
- [ ] Notificaciones de fallo + auto-reintento
- [ ] Métricas de velocidad de upload/download
- [ ] Cifrado en reposo (opcional)
- [ ] Integración con caldav/carddav de O2 (si existe)

## Referencias

- [Home Assistant Integration Development](https://developers.home-assistant.io/docs/integration_index)
- [O2CloudDrive (cliente Windows)](https://github.com/chemyglez/O2CloudDrive)
- [O2 Cloud](https://cloud.o2online.es)
