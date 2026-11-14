<div align="center">

# ☁️ O2 Cloud Backup para Home Assistant

### Tus copias de seguridad de Home Assistant, a salvo en tu nube de O2. Sin discos que se llenan, sin sustos. 🛟

**🇪🇸 Español** · [🇬🇧 English](#-o2-cloud-backup-for-home-assistant-english)

[![Validate](https://github.com/txitxo0/o2cloud-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/txitxo0/o2cloud-ha/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?logo=homeassistantcommunitystore&logoColor=white)](https://hacs.xyz)
[![Versión](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Ftxitxo0%2Fo2cloud-ha%2Fmain%2Fcustom_components%2Fo2cloud%2Fmanifest.json&query=%24.version&label=versi%C3%B3n&logo=homeassistant&color=41BDF5)](https://github.com/txitxo0/o2cloud-ha/releases)
[![Estrellas](https://img.shields.io/github/stars/txitxo0/o2cloud-ha?style=flat&logo=github&color=gold)](https://github.com/txitxo0/o2cloud-ha/stargazers)

</div>

---

¿Se te llena el disco de Home Assistant con cada backup? 😅 Deja de sufrir: usa
tu **O2 Cloud** (el almacenamiento en la nube de O2 / Telefónica) como destino
para tus **copias de seguridad**. Las creas desde Home Assistant como siempre y
vuelan directas a la nube. 📦☁️

**Lo que consigues:**

- 📤 O2 Cloud aparece como una ubicación de backup **nativa** de Home Assistant
  (crear, subir, listar, descargar y borrar copias).
- 📊 Sensores de cuota (total, usado, libre, %) para vigilar tu espacio de un vistazo.
- 🇪🇸 Interfaz en español e inglés.
- 🔒 Tus credenciales nunca salen de tu Home Assistant.

---

## 🔒 Sobre tu privacidad

> Esta integración **no recopila ni envía tus datos a ningún sitio**. Las
> credenciales de sesión se usan **exclusivamente** para autenticarte contra tu
> propia nube de O2 y se guardan en la configuración de Home Assistant. Protege
> tus copias de seguridad y no compartas los tokens ni la URL de retorno.

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

## 2. Añadir la integración

1. **Ajustes → Dispositivos y servicios → Añadir integración → "O2 Cloud"**.
2. Elige el nombre de la carpeta de backups (por defecto: `homeassistant`).
3. Abre el enlace de acceso e inicia sesión en O2. Copia la URL completa de la
  barra de direcciones después de iniciar sesión y pégala en Home Assistant.
4. ¡Listo! Ya puedes usar O2 Cloud en **Ajustes → Sistema → Copias de
   seguridad**.

---

## ⏳ ¿La sesión caduca?

La integración intenta renovar la sesión automáticamente. Si O2 revoca las
credenciales, Home Assistant te pedirá repetir el acceso desde el navegador.
Las instalaciones existentes con cookies siguen funcionando y pasan al nuevo
método al reautenticarse.

## ❓ Problemas frecuentes

- **"Invalid credentials"**: vuelve a abrir el enlace de acceso e iniciar sesión.
- **URL no válida**: copia la dirección completa del mismo intento de acceso.
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
- [uniextra/MovistarWebDAVProxy](https://github.com/uniextra/MovistarWebDAVProxy)
  — referencia para la vinculación OAuth del cliente de escritorio.

## Licencia

MIT

---
---

<div align="center">

# ☁️ O2 Cloud Backup for Home Assistant (English)

### Your Home Assistant backups, safe in your O2 cloud. No more full disks, no more scares. 🛟

[🇪🇸 Español](#-o2-cloud-backup-para-home-assistant) · **🇬🇧 English**

[![Validate](https://github.com/txitxo0/o2cloud-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/txitxo0/o2cloud-ha/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?logo=homeassistantcommunitystore&logoColor=white)](https://hacs.xyz)
[![Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Ftxitxo0%2Fo2cloud-ha%2Fmain%2Fcustom_components%2Fo2cloud%2Fmanifest.json&query=%24.version&label=version&logo=homeassistant&color=41BDF5)](https://github.com/txitxo0/o2cloud-ha/releases)
[![Stars](https://img.shields.io/github/stars/txitxo0/o2cloud-ha?style=flat&logo=github&color=gold)](https://github.com/txitxo0/o2cloud-ha/stargazers)

</div>

---

Tired of your Home Assistant disk filling up with every backup? 😅 Stop the pain:
use your **O2 Cloud** (the O2 / Telefónica personal cloud storage) as a
destination for your **backups**. Create them from Home Assistant as usual and
they fly straight to the cloud. 📦☁️

**What you get:**

- 📤 O2 Cloud shows up as a **native** Home Assistant backup location
  (create, upload, list, download and delete backups).
- 📊 Quota sensors (total, used, free, %) to keep an eye on your space at a glance.
- 🇪🇸 Spanish and English interface.
- 🔒 Your credentials never leave your Home Assistant.

> ℹ️ O2 Cloud is a Spanish service (O2 / Telefónica España), but this guide is
> provided in English so anyone can set it up.

---

## 🔒 About your privacy

> This integration **does not collect or send your data anywhere**. The
> session credentials are used **only** to authenticate against your own O2
> cloud and are stored in Home Assistant's configuration. Protect your backups
> and do not share the tokens or the callback URL.

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

## 2. Add the integration

1. **Settings → Devices & services → Add integration → "O2 Cloud"**.
2. Choose the backup folder name (default: `homeassistant`).
3. Open the sign-in link and log in to O2. Copy the complete URL from the
  address bar after signing in and paste it into Home Assistant.
4. Done! You can now use O2 Cloud under **Settings → System → Backups**.

---

## ⏳ Does the session expire?

The integration attempts to renew the session automatically. If O2 revokes the
credentials, Home Assistant will ask you to sign in again. Existing cookie-based
installations continue to work and switch to OAuth when re-authenticated.

## ❓ Troubleshooting

- **"Invalid credentials"**: open the sign-in link again and sign in.
- **Invalid URL**: copy the complete address from the same sign-in attempt.
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
- [uniextra/MovistarWebDAVProxy](https://github.com/uniextra/MovistarWebDAVProxy)
  — reference for desktop-client OAuth pairing.

## License

MIT

