# Guía de inicio rápido: O2 Cloud Backup

## 1. Extraer credenciales (5 min)

### Paso A: Abrir sesión en O2 Cloud

1. Ve a https://cloud.o2online.es
2. Inicia sesión con tu móvil/email y contraseña
3. Introduce el código SMS si es necesario

### Paso B: Activar Herramientas de desarrollo

1. Presiona `F12` para abrir Developer Tools
2. Ve a la pestaña `Network`
3. Si está vacío, recarga la página (Ctrl+R)

### Paso C: Extraer `validationkey`

1. En la pestaña Network, busca una request a `/sapi/media`
2. Haz clic en ella
3. Ve a la pestaña `Headers`
4. Busca en `Request URL` el parámetro `validationkey=...`
5. Copia el valor después del `=`

   Ejemplo:
   ```
   https://cloud.o2online.es/sapi/media?action=get-storage-space&validationkey=ABC123DEF456...
   ```
   Tu `validationkey` es: `ABC123DEF456...`

### Paso D: Extraer `User-Agent`

1. En la misma request, busca el header `User-Agent` en `Request Headers`
2. Copia el valor completo

   Ejemplo:
   ```
   User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...
   ```

### Paso E: (Opcional) Extraer cookies

1. En `Request Headers`, busca `Cookie:`
2. Copia el contenido completo
3. Si es muy largo, puedes dejar este campo vacío (no es estrictamente necesario)

## 2. Configurar en Home Assistant (5 min)

1. Abre Home Assistant
2. Ve a **Ajustes** → **Dispositivos e integraciones**
3. Haz clic en **Crear automatización** (esquina inferior derecha)
4. Busca **"O2 Cloud Backup"** en el buscador
5. Haz clic para iniciar la configuración

**Campos a rellenar:**

| Campo | Ejemplo | Notas |
|-------|---------|-------|
| **Validation Key** | `ABC123DEF456...` | Obligatorio, del paso C |
| **User-Agent** | `Mozilla/5.0...` | Obligatorio, del paso D |
| **Folder Name** | `backups` | Nombre de carpeta en O2 Cloud |
| **Folder ID** | `root` | Dejar por defecto |
| **Refresh Interval** | `30` | Minutos, 15-120 |
| **Include Soft Deleted** | No | Sí incluir papelera en cuota |

6. Haz clic en **Crear entrada**

## 3. Verificar que funciona (2 min)

En **Herramientas de desarrollo** → **Servicios**, busca:

```yaml
service: o2cloud_backup.test_connection
```

Si ves en los logs:
```
Connection test result: True
```

¡Está configurado correctamente!

## 4. Usar la integración

### Ver cuota en el dashboard

Ve a **Panel principal** y añade los sensores:
- `sensor.o2cloud_total_bytes`
- `sensor.o2cloud_used_percent`
- `binary_sensor.o2cloud_session_valid`

### Subir un backup manualmente

En **Herramientas de desarrollo** → **Servicios**:

```yaml
service: o2cloud_backup.upload_backup
data:
  file_path: /config/backups/core_2024_07_06_12_30_45.tar
```

Reemplaza la ruta por tu archivo de backup real. Lo encuentras en **Ajustes** → **Sistema** → **Copias de seguridad**.

### Automatizar subidas

Crea una automatización que suba backups automáticamente:

```yaml
alias: "Backup automático a O2 Cloud"
trigger:
  - platform: time
    at: "03:00:00"  # Cada día a las 3:00 AM
action:
  - service: hassio.create_snapshot
    data:
      name: "Snapshot {{now().strftime('%Y-%m-%d %H:%M')}}"
  - delay:
      minutes: 10  # Esperar a que se cree
  - service: o2cloud_backup.refresh_quota
  - service: persistent_notification.create
    data:
      title: "Backup realizado"
      message: "Se ha creado y subido el backup a O2 Cloud"
```

## 5. Qué hacer cuando expire la sesión

Esto ocurre cada 2-4 semanas.

1. Verás en el dashboard: `binary_sensor.o2cloud_session_valid` → `OFF`
2. Ve a **Ajustes** → **Dispositivos e integraciones**
3. Haz clic en **O2 Cloud Backup**
4. Haz clic en el botón de **3 puntos** → **Reconfigurar**
5. Extrae nuevas credenciales (repite pasos de "Extraer credenciales")
6. Introduce los nuevos valores

¡Listo!

## Primeros pasos de prueba (recomendado)

1. Configura la integración
2. Deja que actualice los sensores un par de veces (30 min)
3. Prueba `test_connection`
4. Sube un archivo pequeño de prueba
5. Verifica en O2 Cloud que aparezca
6. Una vez confirmado, automatiza los backups

---

**¿Algo no funciona?** Revisa los logs en **Herramientas de desarrollo** → **Logs** y busca mensajes de error con `o2cloud_backup`.
