/**
 * Conector de WhatsApp por código QR para Academic Bot.
 *
 * - No requiere cuenta empresarial de Meta ni Twilio: vinculas tu propio WhatsApp
 *   escaneando el código QR desde "Dispositivos vinculados".
 * - Muestra el QR tanto en la consola como en un panel web local (http://localhost:3005).
 * - Se comunica en tiempo real con el motor Python (`bot.whatsapp.bridge_cli`),
 *   reutilizando los mismos clientes de `academic-api` y `academic-rag`.
 */

const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require("@whiskeysockets/baileys");
const qrcodeTerminal = require("qrcode-terminal");
const QRCode = require("qrcode");
const pino = require("pino");
const http = require("http");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");

const PORT = process.env.WHATSAPP_WEB_PORT || 3005;
const PROJECT_ROOT = path.resolve(__dirname, "..");
const AUTH_DIR = path.join(__dirname, "auth_info_baileys");

let latestQrDataUrl = null;
let connectionStatus = "Esperando generación de código QR...";
let connectedJid = null;
const messageHistory = [];

// -----------------------------------------------------------------------------
// 1. Puente persistente con el motor Python (bot.whatsapp.bridge_cli)
// -----------------------------------------------------------------------------
function resolvePythonBin() {
  const winVenv = path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe");
  const unixVenv = path.join(PROJECT_ROOT, ".venv", "bin", "python");
  if (fs.existsSync(winVenv)) return winVenv;
  if (fs.existsSync(unixVenv)) return unixVenv;
  return "python";
}

let pyProc = null;
let reqCounter = 0;
const pendingRequests = new Map();

function startPythonBridge() {
  const pythonBin = resolvePythonBin();
  pyProc = spawn(pythonBin, ["-m", "bot.whatsapp.bridge_cli"], {
    cwd: PROJECT_ROOT,
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    stdio: ["pipe", "pipe", "inherit"],
  });

  let buffer = "";
  pyProc.stdout.on("data", (chunk) => {
    buffer += chunk.toString("utf-8");
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const data = JSON.parse(line);
        const resolver = pendingRequests.get(data.id);
        if (resolver) {
          pendingRequests.delete(data.id);
          resolver(data);
        }
      } catch (err) {
        console.error("[Puente Python] Error parseando JSON:", err.message);
      }
    }
  });

  pyProc.on("exit", (code) => {
    console.warn(`[Puente Python] Proceso finalizado (${code}). Reiniciando en 2s...`);
    setTimeout(startPythonBridge, 2000);
  });
}

function askPythonProcessor(sender, text) {
  return new Promise((resolve) => {
    const id = String(++reqCounter);
    pendingRequests.set(id, resolve);
    const payload = JSON.stringify({ id, sender, text }) + "\n";
    pyProc.stdin.write(payload, "utf-8");
  });
}

// -----------------------------------------------------------------------------
// 2. Conexión a WhatsApp Web con @whiskeysockets/baileys
// -----------------------------------------------------------------------------
async function connectToWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    logger: pino({ level: "silent" }),
    printQRInTerminal: false,
    auth: state,
    browser: ["Academic Bot (UCP)", "Chrome", "1.0.0"],
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      connectionStatus = "Escanea el código QR desde tu WhatsApp → Dispositivos vinculados";
      console.log("\n==============================================================");
      console.log(" 📱 ESCANEA ESTE CÓDIGO QR EN TU WHATSAPP (Dispositivos vinculados)");
      console.log(` 🌐 O ábrelo más grande en tu navegador: http://localhost:${PORT}`);
      console.log("==============================================================\n");
      qrcodeTerminal.generate(qr, { small: true });
      try {
        latestQrDataUrl = await QRCode.toDataURL(qr, { width: 320, margin: 2 });
      } catch (_) {}
    }

    if (connection === "close") {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      connectionStatus = shouldReconnect
        ? "Reconectando con WhatsApp..."
        : "Sesión cerrada. Borra auth_info_baileys para generar un nuevo QR.";
      if (shouldReconnect) {
        setTimeout(connectToWhatsApp, 2500);
      }
    } else if (connection === "open") {
      latestQrDataUrl = null;
      connectedJid = sock.user?.id || "Vinculado";
      connectionStatus = `Conectado en WhatsApp como ${connectedJid}`;
      console.log("\n✅ ¡WhatsApp conectado exitosamente a Academic Bot!");
      console.log("💬 Envía /start, /login, /materias, /tareas o /preguntar al chat.\n");
    }
  });

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;

    for (const msg of messages) {
      if (!msg.message) continue;
      const remoteJid = msg.key.remoteJid || "";
      if (remoteJid === "status@broadcast" || remoteJid.endsWith("@g.us")) continue;

      const text =
        msg.message.conversation ||
        msg.message.extendedTextMessage?.text ||
        "";

      if (!text.trim()) continue;

      // Si el mensaje lo envió el mismo teléfono vinculado, solo responder si empieza con "/"
      if (msg.key.fromMe && !text.trim().startsWith("/")) continue;

      console.log(`📩 [WhatsApp ${remoteJid}]: ${text}`);
      const res = await askPythonProcessor(remoteJid, text);

      if (res && res.reply) {
        await sock.sendMessage(remoteJid, { text: res.reply });
        messageHistory.unshift({
          time: new Date().toLocaleTimeString(),
          sender: remoteJid.split("@")[0],
          input: text,
          reply: res.reply,
        });
        if (messageHistory.length > 25) messageHistory.pop();
      }

      // Si el usuario programó un recordatorio con /recordar, agendar el envío en WhatsApp
      if (res && res.reminder && res.reminder.delay_seconds) {
        const delayMs = res.reminder.delay_seconds * 1000;
        const reminderText = res.reminder.text;
        setTimeout(async () => {
          try {
            await sock.sendMessage(remoteJid, { text: reminderText });
          } catch (err) {
            console.error("Error enviando recordatorio en WhatsApp:", err.message);
          }
        }, delayMs);
      }
    }
  });
}

// -----------------------------------------------------------------------------
// 3. Panel Web Local (http://localhost:3005) para escanear el QR cómodamente
// -----------------------------------------------------------------------------
const server = http.createServer((req, res) => {
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end(`<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="refresh" content="4" />
  <title>Academic Bot — Panel WhatsApp QR</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }
    .card { max-width: 720px; margin: 0 auto; background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 24px; }
    .badge { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; background: #10b98122; color: #34d399; border: 1px solid #10b98155; }
    .qr-box { text-align: center; margin: 20px 0; padding: 20px; background: #0f172a; border-radius: 12px; }
    .qr-box img { border-radius: 12px; background: white; padding: 8px; }
    .log { background: #0f172a; padding: 12px; border-radius: 10px; margin-top: 10px; font-size: 13px; border: 1px solid #334155; white-space: pre-wrap; }
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">WhatsApp Web Bridge · Academic Bot</span>
    <h2 style="margin: 10px 0 4px;">Conector WhatsApp por Código QR</h2>
    <p style="color:#94a3b8; margin-top:0;">Estado: <strong>${connectionStatus}</strong></p>
    ${
      latestQrDataUrl
        ? `<div class="qr-box">
             <img src="${latestQrDataUrl}" alt="Código QR de WhatsApp" />
             <p style="font-size:13px; color:#cbd5e1;">Abre WhatsApp en tu celular → <strong>Dispositivos vinculados</strong> → <strong>Vincular un dispositivo</strong></p>
           </div>`
        : `<div class="qr-box" style="color:#34d399; font-weight:600;">
             ${connectedJid ? "✅ Tu WhatsApp está vinculado y respondiendo comandos en vivo." : "⏳ Generando sesión con WhatsApp..."}
           </div>`
    }
    <h3 style="font-size:15px;">Últimos mensajes procesados (${messageHistory.length})</h3>
    ${
      messageHistory.length === 0
        ? `<p style="font-size:13px; color:#64748b;">Envía <code>/start</code>, <code>/login</code>, <code>/materias</code>, <code>/tareas</code> o <code>/preguntar</code> por WhatsApp.</p>`
        : messageHistory
            .map(
              (m) =>
                `<div class="log"><strong>[${m.time}] +${m.sender}:</strong> ${m.input}\n\n${m.reply}</div>`
            )
            .join("")
    }
  </div>
</body>
</html>`);
});

startPythonBridge();
connectToWhatsApp();
server.listen(PORT, () => {
  console.log(`🌐 Panel Web de WhatsApp QR activo en: http://localhost:${PORT}`);
});
