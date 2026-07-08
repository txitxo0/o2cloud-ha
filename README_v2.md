# O2 Cloud Backup para Home Assistant

Integración privada de Home Assistant para usar O2 Cloud como **ubicación de backup** nativa.

## Características

- 🔐 Autenticación y gestión de sesión
- 📊 Sensores de cuota (total, usado, libre, porcentaje)
- 🔄 Actualización periódica de información
- 📤 **Soporte de Backup Platform**: O2 Cloud aparece como ubicación de backup en Ajustes > Sistema > Backups
- ✅ Backups automáticos según programación
- ⚙️ Reautenticación automática cuando caduca la sesión
- 🇪🇸 Interfaz en español e inglés

## Requisitos

- Home Assistant 2025.1.0 o superior
- Acceso a O2 Cloud (https://cloud.o2online.es)
- Capacidad de extraer credenciales desde el navegador

## Instalación

1. Copia este directorio a `custom_components/o2cloud_backup/` en tu instalación de Home Assistant:
   ```
   ~/.homeassistant/custom_components/o2cloud_backup/
   ```

2. Reinicia Home Assistant

3. En Ajustes > Dispositivos e integraciones, busca "O2 Cloud Backup" y configura

## Configuración inicial

### Obtener credenciales

1. Abre https://cloud.o2online.es en tu navegador
2. Inicia sesión
3. Abre Herramientas de desarrollo (F12)
4. Ve a la pestaña "Network"
5. Actualiza la página o realiza una acción
6. Busca una request a `cloud.o2online.es/sapi/`
7. Copia del header `Request` → `User-Agent`
8. Extrae de la URL el parámetro `validationkey`
9. Copia las cookies del header `Cookie` (opcional)

### Configuración en Home Assistant

1. Ve a **Ajustes** → **Dispositivos e integraciones**
2. Crea una nueva integración: "O2 Cloud Backup"
3. Introduce las credenciales extraídas
4. Sigue los pasos de configuración

### Habilitar O2 Cloud como ubicación de backup

1. Ve a **Ajustes** → **Sistema** → **Copias de seguridad**
2. Selecciona **Configurar copias de seguridad automáticas**
3. Bajo **Ubicaciones**, activa **O2 Cloud Backup**
4. Configura tu programación (diaria recomendado)
5. Elige cuántos backups mantener (ej: 7)
6. ¡Listo! Los backups se crearán automáticamente

## Sensores disponibles

| Sensor | Tipo | Descripción |
|--------|------|-------------|
| `sensor.o2cloud_total_bytes` | Bytes | Capacidad total |
| `sensor.o2cloud_used_bytes` | Bytes | Capacidad usada |
| `sensor.o2cloud_free_bytes` | Bytes | Capacidad libre |
| `sensor.o2cloud_used_percent` | % | Porcentaje utilizado |
| `sensor.o2cloud_last_update` | Timestamp | Última actualización |
| `binary_sensor.o2cloud_session_valid` | On/Off | Estado de sesión |

## Seguridad

- ✓ Credenciales en storage cifrado
- ✓ No se escriben en logs
- ✓ Reautenticación periódica
- ✓ API interna (no oficial)

## Solución de problemas

### "Invalid credentials"
- Verifica que validationkey y user-agent sean correctos
- Intenta extraer de nuevo

### "Sesión expirada"
- Normal cada 2-4 semanas
- Reconfigura en Reautenticación

### Sensores unavailable
- Espera 30 min
- Revisa logs

## Licencia

MIT
