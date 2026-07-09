# O2 Cloud Backup para Home Assistant

**🇪🇸 Español** · [🇬🇧 English](#o2-cloud-backup-for-home-assistant-english)

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

## 🙏 Agradecimientos

El mapeo de la API interna de O2 Cloud (Synchronoss OneMediaHub) no habría sido
posible sin estos proyectos de referencia. ¡Gracias a sus autores! 🙌

- [danielperez9430/o2cloud-cli](https://github.com/danielperez9430/o2cloud-cli)
  — CLI de O2 Cloud (flujo de subida en dos pasos y autenticación).
- [garanda21/o2cloud_gateway_webdav](https://github.com/garanda21/o2cloud_gateway_webdav)
  — gateway WebDAV para O2 Cloud (login por navegador y manejo de sesión).

## Licencia

MIT

---
---

# O2 Cloud Backup for Home Assistant (English)

[🇪🇸 Español](#o2-cloud-backup-para-home-assistant) · **🇬🇧 English**

Use your **O2 Cloud** (the O2 / Telefónica personal cloud storage) as a
destination for your Home Assistant **backups**. 📦☁️

- 📤 O2 Cloud shows up as a native Home Assistant backup location
  (create, upload, list, download and delete backups).
- 📊 Quota sensors (total, used, free, %).
- 🇪🇸 Spanish and English interface.

> ℹ️ O2 Cloud is a Spanish service (O2 / Telefónica España), but this guide is
> provided in English so anyone can set it up.

---

## 🔒 About your privacy

> This integration **does not collect or send your data anywhere**. The
> credentials you enter (`validation_key` + session cookies) are used
> **only** to authenticate against your own O2 cloud (`cloud.o2online.es`) and
> are stored in Home Assistant's encrypted storage. They are not passwords:
> they are a session from your browser, used solely to talk to the O2 API on
> your behalf.

---

## 1. Installation

### Option A — HACS (recommended)

1. In HACS: menu (⋮) → **Custom repositories**.
2. Add this repository URL and choose the **Integration** category:
   ```
   https://github.com/txitxo0/o2cloud-ha
   ```
3. Search for **"O2 Cloud"** in HACS, install it and **restart Home Assistant**.

### Option B — Manual

1. Copy the `custom_components/o2cloud/` folder into your Home Assistant config:
   ```
   <config>/custom_components/o2cloud/
   ```
2. Restart Home Assistant.

## 2. Get the credentials JSON

O2 has no public username/password API, so you must log in **once** in a
browser and extract the session. A small script does it for you.

> ⚠️ **Run the script on your own computer** (Windows, macOS or Linux with a
> screen), **NOT** inside Home Assistant. The SSH/Terminal add-on is a
> **headless server**: it can't open the browser or show you the SMS login, so
> the script won't work there. You only need the computer for this step; then
> you paste the JSON into Home Assistant.

1. On your computer, with **Python** installed, run:
   ```bash
   pip install playwright
   python -m playwright install chromium
   python extract_o2_credentials.py
   ```
2. A browser opens. **Log in to O2** (phone number + password + SMS).
3. Once you reach your files, the script **prints a JSON block in the
   terminal**. Copy the whole block and paste it into the integration.

> 💡 The JSON only contains what's needed to authenticate the session. You can
> review it before pasting.

## 3. Add the integration

1. **Settings → Devices & services → Add integration → "O2 Cloud"**.
2. **Paste the JSON** into the single form field.
3. (Optional) Change the backup folder name (default: `homeassistant`).
4. Done! You can now use O2 Cloud under **Settings → System → Backups**.

---

## ⏳ Does the session expire?

The O2 session expires after inactivity (days/weeks). When it does, Home
Assistant will ask you to **re-authenticate**: run
`python extract_o2_credentials.py` **on your computer** again and paste the new
JSON.

## ❓ Troubleshooting

- **"Invalid credentials"**: the JSON is incomplete or the session expired. Run
  the script again and paste the new JSON.
- **Sensors show "unavailable"**: check the logs
  (Settings → System → Logs) and verify the session.

---

## ⚠️ Disclaimer

This integration uses O2 Cloud's internal API (`cloud.o2online.es/sapi/`), which
is **not official** and may change without notice. Personal-use project; review
O2's Terms of Service. No warranty.

## 🙏 Acknowledgements

Mapping O2 Cloud's internal API (Synchronoss OneMediaHub) would not have been
possible without these reference projects. Thanks to their authors! 🙌

- [danielperez9430/o2cloud-cli](https://github.com/danielperez9430/o2cloud-cli)
  — O2 Cloud CLI (two-step upload flow and authentication).
- [garanda21/o2cloud_gateway_webdav](https://github.com/garanda21/o2cloud_gateway_webdav)
  — WebDAV gateway for O2 Cloud (browser-based login and session handling).

## License

MIT

