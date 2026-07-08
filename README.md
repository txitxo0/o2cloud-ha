# O2 Cloud Backup para Home Assistant

Integración privada de Home Assistant para usar O2 Cloud como destino de copias de seguridad.

## Características

- 🔐 Autenticación y gestión de sesión
- 📊 Sensores de cuota (total, usado, libre, porcentaje)
- 🔄 Actualización periódica de información
- 📤 Servicio de subida de backups
- ⚙️ Reautenticación automática cuando caduca la sesión
- 🇪🇸 Interfaz en español y English

## Requisitos

- Home Assistant 2024.12.0 o superior
- Acceso a O2 Cloud (https://cloud.o2online.es)
- Capacidad de extraer credenciales desde el navegador

## Instalación

1. Copia este directorio a `custom_components/o2cloud_backup/` en tu instalación de Home Assistant:
   ```
   ~/.homeassistant/custom_components/o2cloud_backup/
   ```

2. Reinicia Home Assistant

3. En Ajustes > Dispositivos e integraciones, haz clic en "Crear automatización" y busca "O2 Cloud Backup"

## Configuración inicial

### Obtener credenciales

1. Abre https://cloud.o2online.es en tu navegador
2. Inicia sesión
3. Abre Herramientas de desarrollo (F12)
4. Ve a la pestaña "Network"
5. Actualiza la página o realiza una acción (listar archivos, etc.)
6. Busca una request a `cloud.o2online.es/sapi/`
7. Copia del header `Request` → `User-Agent`
8. Extrae de la URL el parámetro `validationkey`
9. Copia las cookies del header `Cookie` (opcional, pero recomendado)

### Configuración en Home Assistant

1. Ve a Ajustes > Dispositivos e integraciones
2. Crea una nueva integración: "O2 Cloud Backup"
3. Introduce las credenciales extraídas:
   - **Validation Key**: el valor del parámetro `validationkey`
   - **User-Agent**: (opcional si no se especifica)
   - **Folder Name**: nombre de la carpeta donde se guardarán backups (ej: "backups")
   - **Folder ID**: ID de la carpeta (por defecto: "root")
4. Elige intervalo de actualización de cuota

## Sensores disponibles

| Sensor | Tipo | Descripción |
|--------|------|-------------|
| `sensor.o2cloud_total_bytes` | Bytes | Capacidad total |
| `sensor.o2cloud_used_bytes` | Bytes | Capacidad usada |
| `sensor.o2cloud_free_bytes` | Bytes | Capacidad libre |
| `sensor.o2cloud_used_percent` | % | Porcentaje utilizado |
| `sensor.o2cloud_last_update` | Timestamp | Última actualización de cuota |
| `binary_sensor.o2cloud_session_valid` | On/Off | Estado de la sesión |

## Servicios

### `o2cloud_backup.upload_backup`

Subir un archivo a O2 Cloud.

```yaml
service: o2cloud_backup.upload_backup
data:
  file_path: /config/backups/my_backup.tar
  remote_name: "backup_2024_07_06.tar"  # opcional
```

### `o2cloud_backup.refresh_quota`

Actualizar forzosamente la información de cuota.

```yaml
service: o2cloud_backup.refresh_quota
```

### `o2cloud_backup.test_connection`

Probar la conexión y validez de la sesión.

```yaml
service: o2cloud_backup.test_connection
```

## Automatización de ejemplo

Subir backup automáticamente tras crear snapshot:

```yaml
alias: Subir backup a O2 Cloud
description: ""
trigger:
  - platform: homeassistant
    event: service_called
    service: hassio.snapshot_full
action:
  - delay:
      minutes: 5  # Esperar a que se cree el backup
  - service: o2cloud_backup.upload_backup
    data:
      file_path: >
        /config/backups/{{ (states.binary_sensor | 
        selectattr('entity_id', 'match', 'backup_') | 
        list | last).attributes.filename }}
  - service: o2cloud_backup.refresh_quota
  - service: persistent_notification.create
    data:
      title: "Backup subido a O2 Cloud"
      message: "El backup se ha subido correctamente"
```

## Seguridad

- Las credenciales se guardan en el almacenamiento seguro de Home Assistant
- No se escriben en logs
- Se pueden limpiar/regenerar manualmente si es necesario
- Reautenticación periódica recomendada (cada 3-6 meses)

## Solución de problemas

### "Invalid credentials"
- Verifica que `validationkey`, `user_agent` y cookies sean correctos
- Las credenciales puede que hayan expirado, intenta extraerlas de nuevo
- Comprueba que no haya caracteres especiales mal codificados

### "Session expired"
- Esto es normal tras algunos días/semanas
- Reconfigura la integración (Ajustes > Dispositivos e integraciones > O2 Cloud > Reautenticar)
- Extrae nuevas credenciales desde el navegador

### Los sensores muestran "unavailable"
- Revisa los logs de Home Assistant (Herramientas de desarrollo > Logs)
- Comprueba que la sesión sea válida
- Intenta el servicio `test_connection`

## Notas técnicas

- La integración usa la API interna de O2 Cloud (`cloud.o2online.es/sapi/`)
- No es una API oficial documentada, por lo que puede cambiar sin aviso
- Para uso personal/privado, asegúrate de revisar los Términos de Servicio de O2
- Se recomienda usar como destino secundario de backups durante las primeras semanas

## Licencia

MIT

## Autor

Creado para uso personal con Home Assistant.
