"""Puente STDIO JSON en tiempo real entre el conector Node.js (Baileys QR) y Python.

El proceso de Node.js mantiene este módulo abierto y envía una línea JSON por cada
mensaje de WhatsApp recibido:
    {"id": "1", "sender": "573001234567@s.whatsapp.net", "text": "/materias"}

Y recibe una línea JSON con la respuesta generada por `WhatsAppCommandProcessor`:
    {"id": "1", "reply": "...", "reminder": null}
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Dict

from bot.whatsapp.processor import whatsapp_processor


async def _process_line(line: str) -> Dict[str, Any]:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return {"id": None, "reply": "Error de formato JSON en el puente WhatsApp.", "reminder": None}

    req_id = payload.get("id")
    sender = str(payload.get("sender") or "whatsapp_user")
    text = str(payload.get("text") or "")

    result = await whatsapp_processor.handle_message(sender_id=sender, raw_text=text)
    return {
        "id": req_id,
        "reply": result.get("reply", ""),
        "reminder": result.get("reminder"),
    }


async def main_loop() -> None:
    """Bucle principal de lectura por stdin y escritura por stdout en UTF-8."""
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        response = await _process_line(line)
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main_loop())
