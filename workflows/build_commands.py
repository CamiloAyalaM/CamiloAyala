#!/usr/bin/env python3
"""
[MA] COMMANDS — Dispatcher de Comandos Telegram
Centraliza TODOS los mensajes entrantes del bot @CamiloAyalaLinkedIn_bot:
  - /generar /scout /analizar /feedback → dispara el workflow correspondiente
  - /estado /temas /metricas            → lee Sheets y responde con datos reales
  - /ayuda /start / desconocido         → mensaje de ayuda
  - callback_query (botones)            → reenvía al WRITER (ma-telegram-v2)

Al finalizar también:
  - Actualiza el webhook del bot de Telegram a este nuevo endpoint
  - Registra los comandos en BotFather vía setMyCommands
"""
import json, uuid, requests

API_KEY  = "N8N_API_KEY_HERE"
BASE_URL = "https://n8n.camiloayala.net/api/v1"
HEADERS  = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}

WRITER_ID    = "p71hf2LpPVg7vcSO"
SHEETS_ID    = "1TmHXCe_68qA8GDZhZfzK-qvOh0H09tZqAF3UI5nWSrI"
TEMAS_GID    = 1090471100
METRICAS_GID = 830260036
CHAT_ID      = "1160149765"
N8N_BASE     = "https://n8n.camiloayala.net"
CRED_SHEETS  = {"id": "59A9Vs89LRQlZq9m", "name": "Google Sheets account"}
CRED_TG      = {"id": "gR2WcHsnoq4oIAuT", "name": "Telegram account"}

def nid(): return str(uuid.uuid4())

# ── Extract bot token from deployed WRITER ─────────────────────────────
def get_bot_token():
    try:
        r = requests.get(f"{BASE_URL}/workflows/{WRITER_ID}", headers=HEADERS, timeout=10)
        for node in r.json().get("nodes", []):
            url = node.get("parameters", {}).get("url", "")
            if "api.telegram.org/bot" in url:
                # URL format: https://api.telegram.org/bot{TOKEN}/method
                token = url.split("/bot")[1].split("/")[0]
                if token and len(token) > 20:
                    return token
    except Exception:
        pass
    return "BOT_TOKEN_HERE"

BOT_TOKEN  = get_bot_token()
TG_API     = f"https://api.telegram.org/bot{BOT_TOKEN}"
WH_BASE    = f"{N8N_BASE}/webhook"

print(f"  Bot token: {'OK (extraído de WRITER)' if BOT_TOKEN != 'BOT_TOKEN_HERE' else 'PLACEHOLDER'}")

# ─── NODE BUILDERS ────────────────────────────────────────────────────

def n_webhook(name, path, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.webhook",
            "typeVersion": 2, "position": pos,
            "parameters": {"httpMethod": "POST", "path": path,
                           "responseMode": "responseNode", "options": {}}}

def n_respond(name, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1, "position": pos,
            "parameters": {"respondWith": "text", "responseBody": "OK", "options": {}}}

def n_code(name, js, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.code",
            "typeVersion": 2, "position": pos, "parameters": {"jsCode": js}}

def n_switch(name, expr, cases, pos):
    rules = [{"conditions": {"options": {}, "conditions": [
        {"id": nid(), "leftValue": expr,
         "operator": {"type": "string", "operation": "equals"}, "rightValue": v}
    ]}} for v in cases]
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.switch",
            "typeVersion": 3.2, "position": pos,
            "parameters": {"mode": "rules", "rules": {"values": rules},
                           "options": {"fallbackOutput": "extra"}}}

def n_http_post(name, url, pos, body_json=None, headers_extra=None):
    p = {"method": "POST", "url": url,
         "options": {"response": {"response": {"neverError": True}}}}
    if headers_extra:
        p["sendHeaders"] = True
        p["headerParameters"] = {"parameters": [{"name": k, "value": v}
                                                  for k, v in headers_extra.items()]}
    if body_json is not None:
        p["sendBody"] = True
        p["specifyBody"] = "json"
        p["jsonBody"] = body_json if isinstance(body_json, str) else json.dumps(body_json)
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2, "position": pos, "parameters": p}

def n_sheets_read(name, sheet_name, gid, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.googleSheets",
            "typeVersion": 4.5, "position": pos,
            "parameters": {
                "documentId": {"__rl": True, "value": SHEETS_ID, "mode": "id"},
                "sheetName":  {"__rl": True, "value": gid, "mode": "list",
                               "cachedResultName": sheet_name},
                "options": {}
            },
            "credentials": {"googleSheetsOAuth2Api": CRED_SHEETS}}

def n_merge_append(name, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.merge",
            "typeVersion": 3, "position": pos,
            "parameters": {"mode": "append", "options": {}}}

def n_tg(name, chat_expr, text_expr, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.telegram",
            "typeVersion": 1.2, "position": pos,
            "parameters": {"chatId": chat_expr, "text": text_expr,
                           "additionalFields": {"parse_mode": "HTML"}},
            "credentials": {"telegramApi": CRED_TG}}

def connect(conn, src, dst, out=0, inp=0):
    if src not in conn: conn[src] = {"main": []}
    while len(conn[src]["main"]) <= out: conn[src]["main"].append([])
    conn[src]["main"][out].append({"node": dst, "type": "main", "index": inp})

# ─── CÓDIGO NODES ─────────────────────────────────────────────────────

CODE_DETECTAR = f'''
// Detecta el tipo de mensaje y extrae metadatos relevantes
const body    = $json.body || $json;
const msg     = body.message || {{}};
const cb      = body.callback_query;
const CHAT_ID = "{CHAT_ID}";

// ── Callback (botón de aprobación) → reenviar al WRITER ──
if (cb) {{
  return [{{ json: {{
    tipo:      'callback',
    chat_id:   String(cb.message?.chat?.id || CHAT_ID),
    full_body: JSON.stringify(body)
  }} }}];
}}

const text    = (msg.text || '').trim();
const chat_id = String(msg.chat?.id || CHAT_ID);

// Solo procesar si viene del chat autorizado (seguridad básica)
// if (chat_id !== CHAT_ID) return [{{ json: {{ tipo: 'ignorar' }} }}];

if (!text.startsWith('/')) {{
  return [{{ json: {{ tipo: 'ignorar' }} }}];
}}

// Normalizar: /cmd@botname → /cmd
const cmd = text.split(' ')[0].toLowerCase().replace(/@[^\\s]+$/, '');

if (['/generar', '/scout', '/analizar', '/feedback'].includes(cmd)) {{
  return [{{ json: {{ tipo: 'trigger', comando: cmd, chat_id }} }}];
}}
if (['/estado', '/temas', '/metricas'].includes(cmd)) {{
  return [{{ json: {{ tipo: 'query', comando: cmd, chat_id }} }}];
}}
// /ayuda, /start, o comando desconocido
return [{{ json: {{ tipo: 'info', comando: cmd, chat_id }} }}];
'''

CODE_PREP_TRIGGER = f'''
const d       = $json;
const WH_BASE = "{WH_BASE}";

const acciones = {{
  '/generar':  {{
    wh:  WH_BASE + '/ma-writer-manual',
    msg: '✍️ <b>Generando post de LinkedIn...</b>\\n\\nTardará 2-3 minutos. Te llega con los botones de aprobación cuando esté listo.'
  }},
  '/scout': {{
    wh:  WH_BASE + '/ma-scout-manual',
    msg: '🔍 <b>Buscando temas nuevos...</b>\\n\\nLos artículos serán procesados y los temas aparecerán en el Sheet en ~1 minuto.'
  }},
  '/analizar': {{
    wh:  WH_BASE + '/ma-analyst-manual',
    msg: '📊 <b>Analizando métricas...</b>\\n\\nProcesando posts de los últimos 45 días. El informe llega por aquí en ~2 minutos.'
  }},
  '/feedback': {{
    wh:  WH_BASE + '/ma-feedback-manual',
    msg: '🔄 <b>Calculando ciclo de aprendizaje semanal...</b>\\n\\nAnalizando correlaciones históricas. El informe llega en ~2 minutos.'
  }},
}};

const accion = acciones[d.comando] || {{ wh: null, msg: '⚙️ Procesando...' }};
return [{{ json: {{
  chat_id:     d.chat_id,
  tg_mensaje:  accion.msg,
  webhook_url: accion.wh
}} }}];
'''

CODE_PREP_INFO = '''
const d   = $json;
const cmd = d.comando || '';

const ayuda_txt = [
  '📋 <b>Comandos disponibles:</b>',
  '',
  '/generar — Genera un post ahora y lo manda a aprobación',
  '/scout — Busca temas nuevos en RSS y artículos',
  '/analizar — Actualiza métricas de engagement',
  '/feedback — Análisis semanal de correlaciones y estrategia',
  '',
  '/estado — Estado del sistema y temas en pipeline',
  '/temas — Top 5 temas pendientes por score',
  '/metricas — Últimas métricas registradas',
  '/ayuda — Esta lista'
].join('\n');

const msgs = {
  '/ayuda':  ayuda_txt,
  '/start':  '👋 Hola Camilo. Soy tu sistema de contenido para LinkedIn.\n\nUsa /ayuda para ver todos los comandos disponibles.',
};

const msg = msgs[cmd] ||
  `Comando <code>${cmd}</code> no reconocido.\n\nUsa /ayuda para ver los comandos disponibles.`;

return [{ json: { chat_id: d.chat_id, tg_mensaje: msg } }];
'''

CODE_FORMATEAR_QUERY = '''
const cmd     = $('Detectar Tipo Mensaje').first().json.comando || '';
const chat_id = $('Detectar Tipo Mensaje').first().json.chat_id || '';
const all     = $input.all().map(i => i.json);

// Separate temas (have id + tema + score) from metricas (have post_id + engagement_rate)
const temas    = all.filter(i => i.id && i.tema && !('engagement_rate' in i && 'post_id' in i));
const metricas = all.filter(i => i.post_id && 'engagement_rate' in i);

let msg = '';

if (cmd === '/estado') {
  const publicados = temas.filter(t => t.estado === 'publicado');
  const pendientes = temas.filter(t => !t.estado || t.estado === 'pendiente' || t.estado === 'disponible');
  const esperando  = temas.filter(t => t.estado === 'esperando_v2');
  const ultimo_pub = publicados
    .sort((a, b) => new Date(b.fecha_pub || 0) - new Date(a.fecha_pub || 0))[0];

  const er_prom = metricas.length
    ? (metricas.reduce((s, m) => s + (parseFloat(m.engagement_rate) || 0), 0) / metricas.length * 100).toFixed(2)
    : '—';

  msg = [
    '🖥️ <b>Estado del Sistema</b>',
    '',
    `Temas disponibles:    ${pendientes.length}`,
    `Esperando aprobación: ${esperando.length}`,
    `Posts publicados:     ${publicados.length}`,
    `Métricas registradas: ${metricas.length}`,
    `ER promedio histórico: ${er_prom}%`,
    '',
    ultimo_pub
      ? `<b>Último publicado:</b>\n${(ultimo_pub.tema_nombre || ultimo_pub.tema || '?').substring(0, 60)}\n${ultimo_pub.fecha_pub || '?'}`
      : '<b>Sin posts publicados aún</b>',
    '',
    '<b>Ciclos automáticos:</b>',
    '  06:00 SCOUT · 14:00 WRITER',
    '  23:00 ANALYST · Dom 07:00 FEEDBACK'
  ].join('\n');

} else if (cmd === '/temas') {
  const pendientes = temas
    .filter(t => !t.estado || t.estado === 'pendiente' || t.estado === 'disponible')
    .sort((a, b) => parseFloat(b.score || 0) - parseFloat(a.score || 0))
    .slice(0, 5);

  if (!pendientes.length) {
    msg = '📋 No hay temas pendientes en el pipeline.\n\nUsa /scout para agregar nuevos.';
  } else {
    msg = ['📋 <b>Top 5 Temas Pendientes</b>', ''].concat(
      pendientes.map((t, i) =>
        `${i + 1}. <b>${(t.tema_nombre || t.tema || '?').substring(0, 50)}</b>\n` +
        `   Área: ${t.area || '?'} · Tono: ${t.tono || '?'} · Score: ${t.score || '?'}`
      )
    ).join('\n');
  }

} else if (cmd === '/metricas') {
  const recientes = metricas
    .sort((a, b) => new Date(b.fecha || 0) - new Date(a.fecha || 0))
    .slice(0, 5);

  const er_vals = metricas
    .map(m => parseFloat(m.engagement_rate) || 0)
    .filter(e => e > 0);
  const er_prom = er_vals.length
    ? (er_vals.reduce((a, b) => a + b, 0) / er_vals.length * 100).toFixed(2)
    : '—';
  const er_max = er_vals.length
    ? (Math.max(...er_vals) * 100).toFixed(2)
    : '—';

  if (!recientes.length) {
    msg = '📊 No hay métricas registradas aún.\n\nUsa /analizar para actualizar.';
  } else {
    msg = [
      '📊 <b>Métricas Recientes</b>',
      `ER promedio: ${er_prom}% · Mejor ER: ${er_max}%`,
      `Total posts con métricas: ${metricas.length}`,
      ''
    ].concat(
      recientes.map(m =>
        `• <b>${(m.tema || m.area || '?').substring(0, 40)}</b>\n` +
        `  ER: ${(parseFloat(m.engagement_rate || 0) * 100).toFixed(2)}% · ` +
        `${m.likes || 0}♥ ${m.comments || 0}💬 · ${m.fecha || '?'}`
      )
    ).join('\n');
  }
}

return [{ json: { chat_id, tg_mensaje: msg } }];
'''

# ─── BUILD ────────────────────────────────────────────────────────────

def build():
    nodes = []
    conn  = {}
    def add(n): nodes.append(n); return n

    # Entry point — replaces ma-telegram-v2 as main bot webhook
    entry   = add(n_webhook("Telegram Entry COMMANDS", "ma-bot-commands", [0, 0]))
    ack     = add(n_respond("ACK Telegram",                                [260, 0]))
    detectar= add(n_code   ("Detectar Tipo Mensaje", CODE_DETECTAR,        [520, 0]))

    # Router: trigger | query | callback | info (default)
    router  = add(n_switch("Switch Tipo", "={{ $json.tipo }}",
                            ["trigger", "query", "callback"], [780, 0]))

    # ── BRANCH 0: TRIGGER (generar/scout/analizar/feedback) ────────────
    prep_tg = add(n_code("Preparar Trigger", CODE_PREP_TRIGGER, [1040, -300]))
    tg_ack  = add(n_tg("TG Ack Trigger",
                        "={{ $json.chat_id }}", "={{ $json.tg_mensaje }}", [1300, -300]))
    call_wh = add(n_http_post(
        "Llamar Workflow Target",
        "={{ $json.webhook_url }}",
        [1560, -300],
        body_json=json.dumps({"trigger": "telegram_command"})
    ))

    # ── BRANCH 1: QUERY (estado/temas/metricas) ─────────────────────────
    leer_t  = add(n_sheets_read("Leer Temas Cmd",   "Temas",    TEMAS_GID,    [1040, 100]))
    leer_m  = add(n_sheets_read("Leer Metricas Cmd","Metricas", METRICAS_GID, [1040, 380]))
    merge_q = add(n_merge_append("Merge Query Data",                           [1300, 200]))
    fmt_q   = add(n_code("Formatear Query", CODE_FORMATEAR_QUERY,             [1560, 200]))
    tg_resp = add(n_tg("TG Respuesta Query",
                        "={{ $json.chat_id }}", "={{ $json.tg_mensaje }}", [1820, 200]))

    # ── BRANCH 2: CALLBACK — forward to WRITER ──────────────────────────
    fwd_cb  = add(n_http_post(
        "Reenviar Callback al WRITER",
        f"{WH_BASE}/ma-telegram-v2",
        [1040, 600],
        body_json="={{ $json.full_body }}"
    ))

    # ── FALLBACK (info/ayuda/start/desconocido) ──────────────────────────
    prep_inf= add(n_code("Preparar Info", CODE_PREP_INFO,                   [1040, -600]))
    tg_info = add(n_tg("TG Respuesta Info",
                        "={{ $json.chat_id }}", "={{ $json.tg_mensaje }}", [1300, -600]))

    # ── CONEXIONES ─────────────────────────────────────────────────────
    connect(conn, entry["name"],    ack["name"])
    connect(conn, entry["name"],    detectar["name"])

    # Switch outputs: 0=trigger, 1=query, 2=callback, default=info
    connect(conn, router["name"],   prep_tg["name"],  out=0)  # trigger
    connect(conn, router["name"],   leer_t["name"],   out=1)  # query
    connect(conn, router["name"],   leer_m["name"],   out=1)  # query (parallel)
    connect(conn, router["name"],   fwd_cb["name"],   out=2)  # callback
    connect(conn, router["name"],   prep_inf["name"], out=3)  # default (info/ayuda)

    connect(conn, detectar["name"], router["name"])

    # Trigger branch
    connect(conn, prep_tg["name"],  tg_ack["name"])
    connect(conn, tg_ack["name"],   call_wh["name"])

    # Query branch
    connect(conn, leer_t["name"],   merge_q["name"], inp=0)
    connect(conn, leer_m["name"],   merge_q["name"], inp=1)
    connect(conn, merge_q["name"],  fmt_q["name"])
    connect(conn, fmt_q["name"],    tg_resp["name"])

    # Info branch
    connect(conn, prep_inf["name"], tg_info["name"])

    return {
        "name": "[MA] COMMANDS — Bot Dispatcher",
        "nodes": nodes,
        "connections": conn,
        "settings": {
            "executionOrder": "v1",
            "saveDataSuccessExecution": "all",
            "saveExecutionProgress": True,
            "saveManualExecutions": True
        },
        "staticData": None
    }


def register_telegram_commands():
    """Registra los comandos en BotFather vía setMyCommands."""
    commands = [
        {"command": "generar",  "description": "Genera un post ahora y lo manda a aprobación"},
        {"command": "scout",    "description": "Busca temas nuevos en RSS y artículos"},
        {"command": "analizar", "description": "Actualiza métricas de engagement"},
        {"command": "feedback", "description": "Análisis semanal de correlaciones y estrategia"},
        {"command": "estado",   "description": "Estado del sistema y temas en pipeline"},
        {"command": "temas",    "description": "Top 5 temas pendientes por score"},
        {"command": "metricas", "description": "Últimas métricas registradas"},
        {"command": "ayuda",    "description": "Lista todos los comandos disponibles"},
    ]
    r = requests.post(f"{TG_API}/setMyCommands",
                      json={"commands": commands}, timeout=10)
    print(f"  setMyCommands: {'OK' if r.json().get('ok') else r.text}")


def update_telegram_webhook(n8n_wf_id):
    """Actualiza el webhook del bot de Telegram al nuevo endpoint."""
    new_url = f"{N8N_BASE}/webhook/ma-bot-commands"
    r = requests.post(f"{TG_API}/setWebhook",
                      json={"url": new_url, "allowed_updates": ["message", "callback_query"]},
                      timeout=10)
    data = r.json()
    print(f"  setWebhook → {new_url}")
    print(f"  Resultado: {'OK — ' + data.get('description','') if data.get('ok') else data}")


if __name__ == "__main__":
    print("Construyendo [MA] COMMANDS — Bot Dispatcher...")
    wf = build()
    print(f"  Nodos: {len(wf['nodes'])}")
    print(f"  Conexiones src: {len(wf['connections'])}")

    r = requests.post(f"{BASE_URL}/workflows", headers=HEADERS, json=wf, timeout=30)
    if r.status_code in (200, 201):
        d   = r.json()
        wid = d.get("id", "?")
        print(f"  ✅ COMMANDS creado — ID: {wid}")
        print(f"  Webhook: {N8N_BASE}/webhook/ma-bot-commands")
        print(f"  UI: {N8N_BASE}/workflow/{wid}")

        # Activar
        ra = requests.post(f"{BASE_URL}/workflows/{wid}/activate", headers=HEADERS, timeout=10)
        print(f"  Activar: {ra.status_code}")

        # Registrar comandos en BotFather
        print("  Registrando comandos en Telegram BotFather...")
        register_telegram_commands()

        # Actualizar webhook del bot
        print("  Actualizando webhook del bot de Telegram...")
        update_telegram_webhook(wid)

    else:
        print(f"  ❌ Error {r.status_code}: {r.text[:600]}")
