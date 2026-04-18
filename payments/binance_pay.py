"""
binance_pay.py – Integración con Binance Pay Merchant API (Pago automático)

Cómo obtener tus credenciales:
1. Ve a https://merchant.binance.com y crea tu cuenta Merchant
2. En el dashboard ve a: Configuración → API Management
3. Genera API Key y API Secret
4. Copia ambos valores en tu archivo .env
"""
import hashlib
import hmac
import json
import time
import uuid
import asyncio
import aiohttp
from config import BINANCE_API_KEY, BINANCE_API_SECRET

# URLs de la API de Binance Pay
BASE_URL = "https://bpay.binanceapi.com"
CREATE_ORDER_URL  = f"{BASE_URL}/binancepay/openapi/v2/order"
QUERY_ORDER_URL   = f"{BASE_URL}/binancepay/openapi/v2/order/query"
CLOSE_ORDER_URL   = f"{BASE_URL}/binancepay/openapi/v2/order/close"


def _make_headers(payload_str: str) -> dict:
    """Genera los headers de autenticación requeridos por Binance Pay."""
    timestamp = str(int(time.time() * 1000))
    nonce = uuid.uuid4().hex[:32].upper()
    # El mensaje a firmar es: timestamp + \n + nonce + \n + payload + \n
    message = f"{timestamp}\n{nonce}\n{payload_str}\n"
    signature = hmac.new(
        BINANCE_API_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha512
    ).hexdigest().upper()
    return {
        "Content-Type": "application/json",
        "BinancePay-Timestamp": timestamp,
        "BinancePay-Nonce": nonce,
        "BinancePay-Certificate-SN": BINANCE_API_KEY,
        "BinancePay-Signature": signature,
    }


async def create_payment(
    order_id: int,
    amount: float,
    service_name: str,
    currency: str = "USDT",
) -> dict:
    """
    Crea una orden de pago en Binance Pay.

    Retorna:
        {
          "prepay_id":    str,   # ID interno de Binance
          "checkout_url": str,   # Link directo para pagar (enviar al usuario)
          "qr_code_url":  str,   # Link de imagen del QR
          "deep_link":    str,   # Link para abrir Binance App directamente
          "expire_time":  int,   # Timestamp de expiración (ms)
        }
    """
    merchant_order_no = f"RESELI-{order_id}-{int(time.time())}"
    payload = {
        "env": {"terminalType": "APP"},
        "merchantTradeNo": merchant_order_no,
        "orderAmount": round(amount, 2),
        "currency": currency,
        "description": f"ReseliBot - {service_name}",
        "goods": {
            "goodsType": "02",           # 02 = digital goods
            "goodsCategory": "Z000",
            "referenceGoodsId": str(order_id),
            "goodsName": service_name,
            "goodsDetail": f"Acceso a {service_name} por 1 mes",
        },
    }
    payload_str = json.dumps(payload)
    headers = _make_headers(payload_str)

    async with aiohttp.ClientSession() as session:
        async with session.post(CREATE_ORDER_URL, headers=headers, data=payload_str) as resp:
            data = await resp.json()

    if data.get("status") != "SUCCESS":
        error_msg = data.get("errorMessage", data.get("code", "Error desconocido"))
        raise Exception(f"Binance Pay error al crear orden: {error_msg}")

    result = data["data"]
    return {
        "prepay_id":    result.get("prepayId", ""),
        "checkout_url": result.get("checkoutUrl", ""),
        "qr_code_url":  result.get("qrcodeLink", ""),
        "deep_link":    result.get("deeplink", ""),
        "expire_time":  result.get("expireTime", 0),
        "merchant_order_no": merchant_order_no,
    }


async def check_payment_status(prepay_id: str) -> str:
    """
    Consulta el estado de una orden.

    Posibles estados:
        INITIAL   – Orden creada, sin pagar aún
        PENDING   – Pago iniciado, en proceso
        PAID      – ✅ Pago confirmado
        CANCELED  – Cancelada
        ERROR     – Error en el pago
        EXPIRED   – Expirada (sin pago en tiempo)
        REFUNDING – En proceso de reembolso
        REFUNDED  – Reembolsada
    """
    payload = json.dumps({"prepayId": prepay_id})
    headers = _make_headers(payload)

    async with aiohttp.ClientSession() as session:
        async with session.post(QUERY_ORDER_URL, headers=headers, data=payload) as resp:
            data = await resp.json()

    if data.get("status") != "SUCCESS":
        return "ERROR"
    return data["data"].get("status", "UNKNOWN")


async def poll_payment(prepay_id: str, timeout_seconds: int = 900, interval: int = 15) -> str:
    """
    Hace polling cada `interval` segundos hasta que el pago sea PAID
    o hasta que pase `timeout_seconds` (por defecto 15 minutos).

    Retorna el estado final: 'PAID' | 'EXPIRED' | 'CANCELED' | 'ERROR'
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = await check_payment_status(prepay_id)
        if status in ("PAID", "CANCELED", "ERROR", "EXPIRED", "REFUNDED"):
            return status
        await asyncio.sleep(interval)
    return "EXPIRED"


async def close_order(prepay_id: str) -> bool:
    """Cierra/cancela una orden de Binance Pay que aún no fue pagada."""
    payload = json.dumps({"prepayId": prepay_id})
    headers = _make_headers(payload)

    async with aiohttp.ClientSession() as session:
        async with session.post(CLOSE_ORDER_URL, headers=headers, data=payload) as resp:
            data = await resp.json()

    return data.get("status") == "SUCCESS"
