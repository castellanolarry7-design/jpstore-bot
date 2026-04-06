# 🛒 JPStore Bot – Guía de Configuración

## Requisitos
- Python 3.11+
- Cuenta en Telegram
- Bot creado con @BotFather

---

## 1. Crear el bot en Telegram

1. Abre Telegram y busca **@BotFather**
2. Envía `/newbot`
3. Elige un nombre: `JPStore AI`
4. Elige un username: `jpstore_ai_bot` (debe terminar en `bot`)
5. Copia el **TOKEN** que te dará BotFather

---

## 2. Obtener tu ID de Telegram (Admin)

1. Busca **@userinfobot** en Telegram
2. Envía `/start`
3. Copia tu **ID numérico** (ej: `123456789`)

---

## 3. Configurar el archivo .env

```bash
cp .env.example .env
```

Edita el archivo `.env` con tus datos:

```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
ADMIN_ID=123456789
USDT_TRC20_ADDRESS=TXxxxxxxxxxxxxxxxxxxxxxxxxxx
USDT_BEP20_ADDRESS=0xxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## 5. Ejecutar el bot

```bash
python bot.py
```

---

## 6. Comandos del bot

| Comando | Descripción |
|---------|-------------|
| `/start` | Menú principal de la tienda |
| `/admin` | Panel de administración (solo admin) |
| `/cancelar` | Cancela la operación actual |

---

## 7. Flujo de compra

```
Usuario → /start
  → Ver Catálogo
    → Selecciona servicio
      → Selecciona método de pago (TRC20 / BEP20 / Binance Pay)
        → Bot muestra dirección y monto exacto
          → Usuario paga y envía comprobante (foto o hash TX)
            → Admin recibe notificación
              → Admin verifica y entrega credenciales
                → Usuario recibe acceso 🎉
```

---

## 8. Panel de Admin (/admin)

- **📋 Pedidos pendientes** – Ver y gestionar pedidos
- **📊 Estadísticas** – Usuarios, ingresos, pedidos
- **👥 Usuarios** – Lista de clientes registrados
- **📢 Broadcast** – Enviar mensaje a todos los usuarios

Para **entregar un pedido**, haz clic en 🚀 ENTREGAR y escribe las credenciales de acceso.

---

## 9. Configurar Binance Pay (Opcional)

1. Crea cuenta en https://merchant.binance.com
2. Ve a API Management y genera credenciales
3. Agrega al `.env`:
   ```env
   BINANCE_API_KEY=tu_api_key
   BINANCE_API_SECRET=tu_api_secret
   ```

---

## 10. Despliegue en servidor (VPS)

Para mantener el bot activo 24/7:

```bash
# Con screen
screen -S jpstore-bot
python bot.py
# Ctrl+A, Ctrl+D para desacoplar

# O con systemd (recomendado para producción)
# Crea /etc/systemd/system/jpstore.service
```

---

## Estructura del proyecto

```
telegram-store-bot/
├── bot.py              # Punto de entrada principal
├── config.py           # Configuración y catálogo de servicios
├── database.py         # Base de datos SQLite asíncrona
├── requirements.txt    # Dependencias Python
├── .env                # Variables de entorno (NO subir a git)
├── .env.example        # Plantilla de configuración
├── handlers/
│   ├── start.py        # /start y menú principal
│   ├── catalog.py      # Catálogo de servicios
│   ├── orders.py       # Creación y seguimiento de pedidos
│   └── admin.py        # Panel de administración
├── utils/
│   ├── keyboards.py    # Teclados inline
│   └── notifications.py # Notificaciones a admins y usuarios
└── payments/
    └── binance_pay.py  # Integración Binance Pay API
```
