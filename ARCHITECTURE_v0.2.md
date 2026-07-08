# Arquitectura correcta: Backup Platform

## Cambio de diseño (v0.2.0)

La integración ha sido rediseñada para implementar correctamente la **Backup Platform de Home Assistant**, en lugar de proporcionar servicios manuales de backup.

### ¿Por qué este cambio?

Home Assistant tiene un sistema integrado para gestionar "ubicaciones de backup" (Backup Locations) que:

1. **Automático**: HA crea backups automáticamente según la programación
2. **Integrado**: Aparece como opción nativa en Ajustes > Sistema > Backups
3. **Gestión completa**: Listar, descargar, restaurar, eliminar backups desde HA
4. **Retención automática**: Política de retención sin intervención manual
5. **Múltiples destinos**: Soportar varios servidores de backup simultáneamente

### Comparación: Antes vs Ahora

**Antes (v0.1 - Incorrecto)**
```yaml
# Servicio manual
service: o2cloud_backup.upload_backup
data:
  file_path: /config/backups/mi_backup.tar
```
- ❌ Requiere servicio manual o automatización
- ❌ No aparece como ubicación de backup en HA
- ❌ Gestión manual de retención
- ❌ No integrado con el sistema de backups

**Ahora (v0.2 - Correcto)**
```
Ajustes > Sistema > Backups > Ubicaciones de backup
- O2 Cloud Backup ✓ (toggled)
```
- ✅ Automático en la UI
- ✅ HA gestiona todo (crear, listar, eliminar, restaurar)
- ✅ Retención automática configurable
- ✅ Completamente integrado

### Implementación técnica

1. **BackupAgent** (no BackupPlatform)
   ```python
   class O2CloudBackupAgent(BackupAgent):
       async def async_upload_backup(...):
           # Subir automáticamente
       
       async def async_list_backups(...):
           # Listar desde O2 Cloud
       
       async def async_delete_backup(...):
           # Eliminar según retención
   ```

2. **Registro automático**
   ```python
   # En __init__.py
   async_get_backup_agents(hass)
   # HA llama esto automáticamente y registra agentes
   ```

3. **Sin intervención del usuario**
   - HA decide cuándo, dónde y cómo hacer backup
   - Usuario solo configura retención y programa en UI

### Métodos implementados

- `async_list_backups()` - Listar backups remotos
- `async_get_backup(id)` - Obtener info de uno
- `async_upload_backup(...)` - Subir nuevo
- `async_download_backup(id)` - Descargar existente
- `async_delete_backup(id)` - Eliminar según retención

### Flujo de backup automático

```
User: Configura "Backup diario a O2 Cloud" en Ajustes > Sistema > Backups
                            ↓
                    HA detecta O2Cloud
                            ↓
                   Cada día a las 3 AM
                            ↓
              HA crea snapshot localmente
                            ↓
          BackupAgent.async_upload_backup()
                            ↓
                  Archivo sube a O2 Cloud
                            ↓
              HA aplica política de retención
                            ↓
         Backups antiguos se eliminan automáticamente
```

### Limitaciones actuales (MVP)

La integración está en MVP. Funcionalidades no incluidas aún:

- [ ] `async_list_backups()`: Aún no lista backups previos (TODO)
- [ ] `async_download_backup()`: No implementado (TODO)
- [ ] Metadatos comple

tos en O2 Cloud
- [ ] Caché inteligente de backups

### Roadmap

1. **v0.2** (Actual): Estructura correcta con BackupAgent
2. **v0.3**: Implementar `async_list_backups()` completo
3. **v0.4**: Implementar `async_download_backup()`
4. **v0.5**: Soporte para restauración desde O2 Cloud
5. **v1.0**: Características avanzadas (versionado, compresión, etc)

### Ideas / mejoras pendientes (por evaluar)

- [ ] **Logo de O2 para la integración**
  - Fuente: https://web.static.o2online.es/media/public/logo-o2-blue.svg (guardado en `custom_components/o2cloud/brand/logo-o2-blue.svg`)
  - HA no muestra logos desde archivos locales: requiere `icon.png` (256×256) y `logo.png` en el repo oficial `home-assistant/brands` (indexado por `domain`).
  - Para uso privado se queda el icono genérico salvo que se envíe PR a `brands`.
- [ ] **Mejorar la puesta en marcha (extractor de credenciales)**
  - Restricción: el extractor necesita navegador real (Playwright/Chromium); HA corre headless, así que NO puede lanzarse dentro de la integración para autorrellenar.
  - Alcanzable: helper externo más fluido (runner de doble clic, copiar JSON al portapapeles) + el config flow que ya autorrellena pegando el JSON.
  - Opcional avanzado: el extractor sirve una mini-página local con botón "copiar para HA".
- [ ] **Autenticación duradera / automática (evitar reauth cada ~24h)**
  - Hechos: la API no envía `Set-Cookie` por petición; `JSESSIONID` ~24h, `validationKey` ~15 días.
  - A favor: el cliente envía cookies explícitas (ignora `expires`), así que si el servidor usa sesión deslizante, el sondeo cada 30 min podría mantenerla viva >24h. **Experimento 1**: verificar si aguanta >24h sin reauth.
  - Re-login sin SMS: en el SSO `t3.o2online.es` hay cookies HttpOnly de posible "dispositivo de confianza". Si persisten y saltan el SMS, se podría automatizar un re-login usuario+contraseña. **Experimento 2**: modo `--capture-login` en el extractor para registrar el POST de login y confirmar el path sin-SMS.
  - El SMS 2FA no se automatiza; estrategia = keep-alive + re-login con dispositivo de confianza + fallback al reauth manual (pegar JSON).
- [ ] **Compatibilidad con Movistar Cloud (misma plataforma que O2 Cloud)**
  - Hipótesis: la nube de O2 cuelga de Telefónica/Movistar; probablemente el mismo backend (`/sapi/...`) sirva a usuarios de Movistar.
  - Indicio: `cloud.movistar.es` existe (redirige a la página de producto `movistar.es/movistar-cloud`).
  - **Investigar**: dominio real de la app de Movistar Cloud, si usa el mismo `sapi` + `validationkey` + cookies, y si el extractor/cliente funcionan cambiando solo el host base.
  - Si coincide: parametrizar `API_BASE_URL`/`UPLOAD_BASE_URL` por proveedor (o2/movistar) en `const.py` y en el config flow.



### Referencias

- [HA Backup Documentation](https://www.home-assistant.io/common-tasks/general/#backups)
- [OneDrive Integration (referencia)](https://github.com/home-assistant/core/tree/dev/homeassistant/components/onedrive)
- [Backup Platform API](https://developers.home-assistant.io/docs/integrations/backup/)

### Migración desde v0.1

Si usabas v0.1 con servicios manuales:

1. Desinstala v0.1
2. Instala v0.2
3. Reconfigura la integración
4. Ve a Ajustes > Sistema > Backups
5. Activa "O2 Cloud Backup" como ubicación
6. Configura tu programación de backups

¡Eso es todo! Ahora es completamente automático.
