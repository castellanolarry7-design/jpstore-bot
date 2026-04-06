# 🚀 Deploy JPStoreX Bot — Gratis 24/7

Opciones para correr el bot sin tu computadora, completamente gratis.

---

## ✅ OPCIÓN 1 — Railway (Recomendado, más fácil)

**Gratis:** $5 USD de crédito al mes (suficiente para un bot ligero)
**Sin tarjeta de crédito requerida** con cuenta GitHub

### Pasos:

1. **Sube tu código a GitHub**
   - Ve a https://github.com/new y crea un repositorio privado (ej: `jpstorex-bot`)
   - En tu carpeta del bot abre una terminal y ejecuta:
   ```bash
   git init
   git add .
   git commit -m "first commit"
   git remote add origin https://github.com/TU_USUARIO/jpstorex-bot.git
   git push -u origin main
   ```
   > ⚠️ Antes de hacer push, crea un archivo `.gitignore` con el contenido de abajo

2. **Crear `.gitignore`** (importante para no subir tu .env)
   ```
   .env
   store.db
   __pycache__/
   *.pyc
   ```

3. **Crea cuenta en Railway**
   - Ve a https://railway.app
   - Haz clic en **Start a New Project**
   - Selecciona **Deploy from GitHub repo**
   - Conecta tu cuenta de GitHub y elige el repo `jpstorex-bot`

4. **Configura las variables de entorno**
   - En Railway, ve a tu proyecto → **Variables**
   - Agrega cada variable de tu `.env`:
   ```
   BOT_TOKEN        = 8598414802:AAF8...
   ADMIN_ID         = 7098207128
   USDT_TRC20_ADDRESS = TBXbTS...
   USDT_BEP20_ADDRESS = 0x5d1b...
   BINANCE_PAY_ID   = 800595536
   DATABASE_PATH    = store.db
   ```

5. **Crea el archivo `Procfile`** en la raíz del proyecto:
   ```
   worker: python bot.py
   ```

6. **Haz deploy**
   - Railway detectará el `Procfile` y lanzará el bot automáticamente
   - Ve a **Deployments** para ver los logs en tiempo real

---

## ✅ OPCIÓN 2 — Render (100% Gratis, nunca duerme con worker)

**Gratis:** Background Workers gratuitos (no se duermen como los web servers)

### Pasos:

1. Sube el código a GitHub (igual que arriba)

2. Ve a https://render.com → **New** → **Background Worker**

3. Conecta tu repo de GitHub

4. Configura:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`

5. En **Environment Variables** agrega las mismas variables que en Railway

6. Haz clic en **Create Background Worker** — ¡listo!

---

## ✅ OPCIÓN 3 — Oracle Cloud (MEJOR OPCIÓN: siempre gratis, sin límite)

Oracle ofrece una VM gratuita **para siempre** (no expira, no tiene límite mensual).

### Pasos:

1. Crea cuenta en https://cloud.oracle.com/free
   - Requiere tarjeta de crédito para verificación (no te cobra nada)

2. Crea una VM:
   - Ve a **Compute** → **Instances** → **Create Instance**
   - Elige imagen: **Ubuntu 22.04**
   - Shape: **VM.Standard.E2.1.Micro** (Always Free)
   - Descarga la llave SSH que te da Oracle

3. Conéctate a la VM por SSH:
   ```bash
   ssh -i tu_llave.key ubuntu@IP_DE_TU_VM
   ```

4. Instala Python y dependencias:
   ```bash
   sudo apt update && sudo apt install python3 python3-pip git -y
   git clone https://github.com/TU_USUARIO/jpstorex-bot.git
   cd jpstorex-bot
   pip3 install -r requirements.txt
   ```

5. Crea el archivo `.env` en la VM:
   ```bash
   nano .env
   # Pega tu configuración, guarda con Ctrl+O, sal con Ctrl+X
   ```

6. Corre el bot en background con `screen`:
   ```bash
   screen -S jpstore
   python3 bot.py
   # Presiona Ctrl+A, luego D para desacoplar
   # El bot sigue corriendo aunque cierres la terminal
   ```

7. Para volver a ver los logs:
   ```bash
   screen -r jpstore
   ```

---

## 📦 Archivo `requirements.txt` para el deploy

Asegúrate de que tu `requirements.txt` tenga:
```
python-telegram-bot==21.6
python-dotenv==1.0.0
aiohttp==3.11.11
aiosqlite==0.20.0
requests==2.31.0
```

---

## 🏆 Comparación rápida

| Plataforma | Costo | Duerme | Dificultad | Recomendado para |
|---|---|---|---|---|
| **Railway** | $5 crédito/mes | No | ⭐ Muy fácil | Empezar rápido |
| **Render** | Gratis | No (worker) | ⭐⭐ Fácil | 100% gratis |
| **Oracle Cloud** | Gratis siempre | No | ⭐⭐⭐ Medio | Largo plazo |

---

## 🔒 Seguridad importante

Nunca subas tu archivo `.env` a GitHub. Verifica que esté en `.gitignore` antes de hacer push.
