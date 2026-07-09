# O2 Cloud Backup para Home Assistant

Usa tu **O2 Cloud** (el almacenamiento en la nube de O2 / Telefónica) como
destino para las **copias de seguridad** de Home Assistant. 📦☁️

- 📤 O2 Cloud aparece como una ubicación de backup nativa de Home Assistant
  (crear, subir, listar, descargar y borrar copias).
- 📊 Sensores de cuota (total, usado, libre, %).
- 🇪🇸 Interfaz en español e inglés.

---

## 🔒 Sobre tu privacidad

> Esta integración **no recopila ni envía tus datos a ningún sitio**. Las
> credenciales que introduces (`validation_key` + cookies de sesión) se usan
> **exclusivamente** para autenticarte contra tu propia nube de O2
> (`cloud.o2online.es`) y se guardan en el almacenamiento cifrado de Home
> Assistant. No son contraseñas: son una sesión de tu navegador, y solo sirven
> para hablar con la API de O2 en tu nombre.

---

## 1. Instalación

### Opción A — HACS (recomendada)

1. En HACS: menú (⋮) → **Repositorios personalizados**.
2. Añade la URL de este repositorio y elige la categoría **Integration**:
   ```
   https://github.com/txitxo0/o2cloud-ha
   ```
3. Busca **"O2 Cloud"** en HACS, instálala y **reinicia Home Assistant**.

### Opción B — Manual

1. Copia la carpeta `custom_components/o2cloud/` dentro de la config de tu
   Home Assistant:
   ```
   <config>/custom_components/o2cloud/
   ```
2. Reinicia Home Assistant.

## 2. Obtener el JSON de credenciales

O2 no tiene una API pública con usuario y contraseña, así que hay que iniciar
sesión **una vez** en un navegador y extraer la sesión. Lo hace un pequeño
script por ti.

> ⚠️ **Ejecuta el script en tu ordenador** (Windows, macOS o Linux con
> pantalla), **NO** dentro de Home Assistant. El add-on de SSH/Terminal es un
> servidor **sin escritorio**: no puede abrir el navegador ni mostrarte el
> login con SMS, así que el script no funciona ahí. Solo necesitas el ordenador
> para este paso; luego pegas el JSON en Home Assistant.

1. En tu ordenador, con **Python** instalado, ejecuta:
   ```bash
   pip install playwright
   python -m playwright install chromium
   python extract_o2_credentials.py
   ```
2. Se abrirá un navegador. **Inicia sesión en O2** (teléfono + contraseña + SMS).
3. Cuando entres a tus archivos, el script **imprime en la terminal un bloque
   JSON**. Cópialo entero y pégalo en la integración.

> 💡 El JSON solo contiene lo necesario para autenticar la sesión. Puedes
> revisarlo antes de pegarlo.

## 3. Añadir la integración

1. **Ajustes → Dispositivos y servicios → Añadir integración → "O2 Cloud"**.
2. **Pega el JSON** en el único campo del formulario.
3. (Opcional) Cambia el nombre de la carpeta de backups (por defecto:
   `homeassistant`).
4. ¡Listo! Ya puedes usar O2 Cloud en **Ajustes → Sistema → Copias de
   seguridad**.

---

## ⏳ ¿La sesión caduca?

La sesión de O2 caduca por inactividad (días/semanas). Cuando ocurra, Home
Assistant te pedirá **reautenticar**: vuelve a ejecutar
`python extract_o2_credentials.py` **en tu ordenador** y pega el nuevo JSON.

## ❓ Problemas frecuentes

- **"Invalid credentials"**: el JSON está incompleto o la sesión caducó. Vuelve
  a ejecutar el script y pega el nuevo JSON.
- **Los sensores aparecen "unavailable"**: revisa los logs
  (Ajustes → Sistema → Registros) y comprueba la sesión.

---

## ⚠️ Aviso

Esta integración usa la API interna de O2 Cloud (`cloud.o2online.es/sapi/`), que
**no es oficial** y puede cambiar sin previo aviso. Proyecto de uso personal;
revisa los Términos de Servicio de O2. Sin garantía.

## Licencia

MIT

