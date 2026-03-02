#!/usr/bin/env python3
"""
[MA] SCOUT — Descubridor Autónomo de Temas
Corre diariamente a las 6 AM:
  1. Fetch RSS de 4 fuentes de diseño/educación/comunicación
  2. Parsea artículos recientes (últimas 48h)
  3. Jina Reader extrae texto limpio de los top 5 artículos
  4. Qwen analiza y extrae 3 ángulos de tema para Camilo
  5. Escribe nuevos temas en Google Sheets
  6. Notifica por Telegram
"""
import json, uuid, requests

API_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0YmY4ODRkNC1hMGUxLTRiNjgtOTVlZC1kMDc0ZWY5N2ExZDQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOWY0MWY5OWQtZDNkNy00NWNjLWFkZjAtZjc2ZmMwZDQxZjcyIiwiaWF0IjoxNzcxNzcyMzg4fQ.RmQl5yX4T9pAUn4swhvMcydMv-8VukNnlbPc7NgbK0U"
BASE_URL = "https://n8n.camiloayala.net/api/v1"
HEADERS  = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}

SHEETS_ID   = "1TmHXCe_68qA8GDZhZfzK-qvOh0H09tZqAF3UI5nWSrI"
TEMAS_GID   = 1090471100
CHAT_ID     = "1160149765"
BOT_TOKEN   = "BOT_TOKEN"
QWEN        = "qwen2.5:32b"
CRED_SHEETS = {"id": "59A9Vs89LRQlZq9m", "name": "Google Sheets account"}
CRED_OLLAMA = {"id": "S4LeOiFztrgDaMM9", "name": "Ollama"}
CRED_TG     = {"id": "gR2WcHsnoq4oIAuT", "name": "Telegram account"}

def nid(): return str(uuid.uuid4())

def n_schedule(name, cron, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.1, "position": pos,
            "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": cron}]}}}

def n_webhook(name, path, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.webhook",
            "typeVersion": 2, "position": pos,
            "parameters": {"httpMethod": "POST", "path": path, "responseMode": "lastNode", "options": {}}}

def n_code(name, js, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.code",
            "typeVersion": 2, "position": pos, "parameters": {"jsCode": js}}

def n_http(name, method, url, pos, headers_extra=None):
    p = {"method": method.upper(), "url": url,
         "options": {"response": {"response": {"neverError": True}}}}
    if headers_extra:
        p["sendHeaders"] = True
        p["headerParameters"] = {"parameters": [{"name": k, "value": v}
                                                  for k,v in headers_extra.items()]}
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2, "position": pos, "parameters": p}

def n_http_body(name, method, url, pos, body_json, headers_extra=None):
    p = {"method": method.upper(), "url": url, "sendBody": True,
         "specifyBody": "json", "jsonBody": body_json if isinstance(body_json, str) else json.dumps(body_json),
         "options": {"response": {"response": {"neverError": True}}}}
    if headers_extra:
        p["sendHeaders"] = True
        p["headerParameters"] = {"parameters": [{"name": k, "value": v}
                                                  for k,v in headers_extra.items()]}
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2, "position": pos, "parameters": p}

def n_llm(name, sys_p, user_p, temp, max_tok, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.openAi",
            "typeVersion": 1.7, "position": pos,
            "parameters": {
                "modelId": {"__rl": True, "value": QWEN, "mode": "list",
                            "cachedResultName": "QWEN2.5:32B"},
                "messages": {"values": [
                    {"content": sys_p, "role": "system"},
                    {"content": user_p}
                ]},
                "options": {"maxTokens": max_tok, "temperature": temp}
            },
            "credentials": {"openAiApi": CRED_OLLAMA}}

def n_sheets_read(name, sheet_name, gid, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.googleSheets",
            "typeVersion": 4.5, "position": pos,
            "parameters": {
                "documentId": {"__rl": True, "value": SHEETS_ID, "mode": "id"},
                "sheetName": {"__rl": True, "value": gid, "mode": "list",
                              "cachedResultName": sheet_name},
                "options": {}
            },
            "credentials": {"googleSheetsOAuth2Api": CRED_SHEETS}}

def n_sheets_append(name, gid, sheet_name, cols_map, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.googleSheets",
            "typeVersion": 4.5, "position": pos,
            "parameters": {
                "operation": "append",
                "documentId": {"__rl": True, "value": SHEETS_ID, "mode": "id"},
                "sheetName": {"__rl": True, "value": gid, "mode": "list",
                              "cachedResultName": sheet_name},
                "columns": {"mappingMode": "defineBelow", "value": cols_map,
                            "matchingColumns": [], "schema": []},
                "options": {}
            },
            "credentials": {"googleSheetsOAuth2Api": CRED_SHEETS}}

def n_tg(name, chat_id, text, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.telegram",
            "typeVersion": 1.2, "position": pos,
            "parameters": {"chatId": chat_id, "text": text,
                           "additionalFields": {"parse_mode": "HTML"}},
            "credentials": {"telegramApi": CRED_TG}}

def connect(conn, src, dst, out=0, inp=0):
    if src not in conn: conn[src] = {"main": []}
    while len(conn[src]["main"]) <= out: conn[src]["main"].append([])
    conn[src]["main"][out].append({"node": dst, "type": "main", "index": inp})

# ─── CÓDIGO NODES ─────────────────────────────────────────────────────

CODE_RSS_SOURCES = '''
// Fuentes RSS gratuitas de diseño, educación y comunicación
// Seleccionadas para la audiencia de Camilo: creativos, directores, fundadores en Colombia/Latam
const fuentes = [
  { url: "https://uxdesign.cc/feed",                    area: "diseño",        nombre: "UX Design CC" },
  { url: "https://www.fastcompany.com/section/design/rss", area: "diseño",     nombre: "Fast Company Design" },
  { url: "https://medium.com/feed/tag/design-thinking",  area: "diseño",       nombre: "Medium Design Thinking" },
  { url: "https://hbr.org/resources/rss/articles",       area: "liderazgo",    nombre: "Harvard Business Review" },
  { url: "https://ideo.com/journal.rss",                 area: "innovación",   nombre: "IDEO Journal" },
  { url: "https://medium.com/feed/tag/design-education", area: "educación",    nombre: "Medium Design Education" }
];
return fuentes.map(f => ({ json: f }));
'''

CODE_PARSE_RSS = r'''
// Parsear XML RSS y extraer artículos recientes
const items = $input.all();
const ahora = Date.now();
const limite48h = ahora - (48 * 60 * 60 * 1000);
let articulos = [];

for (const item of items) {
  const { area, nombre, url: feed_url } = item.json;
  // El body viene del HTTP Request como texto XML
  const body = item.json.data || item.json.body || '';
  if (!body || typeof body !== 'string') continue;

  // Extraer items del RSS/Atom
  const itemRegex = /<item[^>]*>([\s\S]*?)<\/item>|<entry[^>]*>([\s\S]*?)<\/entry>/gi;
  let match;
  while ((match = itemRegex.exec(body)) !== null) {
    const bloque = match[1] || match[2] || '';

    // Título
    const titleM = bloque.match(/<title[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/title>/i);
    const titulo = titleM ? titleM[1].trim().replace(/<[^>]+>/g,'').substring(0,150) : '';

    // URL
    const linkM = bloque.match(/<link[^>]*href=["'](https?[^"']+)["']|<link[^>]*>(https?[^<]+)<\/link>/i);
    const link = linkM ? (linkM[1]||linkM[2]||'').trim() : '';

    // Fecha
    const fechaM = bloque.match(/<pubDate[^>]*>([\s\S]*?)<\/pubDate>|<published[^>]*>([\s\S]*?)<\/published>|<updated[^>]*>([\s\S]*?)<\/updated>/i);
    const fechaStr = fechaM ? (fechaM[1]||fechaM[2]||fechaM[3]||'').trim() : '';
    const fechaMs = fechaStr ? new Date(fechaStr).getTime() : 0;

    // Descripción corta
    const descM = bloque.match(/<description[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/description>|<summary[^>]*>([\s\S]*?)<\/summary>/i);
    const desc = descM ? (descM[1]||descM[2]||'').replace(/<[^>]+>/g,'').trim().substring(0,300) : '';

    if (!titulo || !link) continue;
    // Incluir si es reciente (48h) o si no tiene fecha (incertidumbre — incluir igual)
    if (fechaMs > 0 && fechaMs < limite48h) continue;

    articulos.push({ titulo, link, fecha: fechaStr, descripcion: desc, area, fuente: nombre });
  }
}

// Ordenar por fecha (más recientes primero), limitar a top 8
articulos.sort((a, b) => {
  const fa = a.fecha ? new Date(a.fecha).getTime() : 0;
  const fb = b.fecha ? new Date(b.fecha).getTime() : 0;
  return fb - fa;
});

if (articulos.length === 0) {
  // Si no hay artículos recientes, tomar los de HN/otros sin filtro de fecha
  return [{ json: { sin_articulos: true, mensaje: 'No se encontraron artículos en las últimas 48h' } }];
}

const top = articulos.slice(0, 8);
return top.map(a => ({ json: a }));
'''

CODE_PREP_JINA = r'''
// Preparar URL de Jina Reader para cada artículo
const art = $json;
const jina_url = 'https://r.jina.ai/' + encodeURI(art.link || '');
return [{ json: { ...art, jina_url } }];
'''

CODE_COMBINAR_ART = r'''
// Combinar todos los artículos extraídos por Jina en un solo texto para análisis
const items = $input.all();
let combinado = '';
const articulos_meta = [];

for (let i = 0; i < items.length; i++) {
  const item = items[i].json;
  // Jina devuelve el texto limpio directamente como string en el body
  const texto = String(item.data || item.body || item.content || '').trim().substring(0, 1500);
  if (!texto) continue;
  combinado += `\n\n=== ARTÍCULO ${i+1}: ${item.titulo||''} (${item.fuente||''}) ===\n${texto}`;
  articulos_meta.push({ titulo: item.titulo, link: item.link, area: item.area, fuente: item.fuente });
}

if (!combinado.trim()) {
  throw new Error('No se pudo extraer texto de ningún artículo via Jina Reader');
}

return [{ json: { texto_combinado: combinado.substring(0, 12000), articulos_meta } }];
'''

CODE_PARSEAR_TEMAS = r'''
const raw = $json.message?.content || $json.choices?.[0]?.message?.content || '';
if (!raw) throw new Error('Scout Qwen no devolvió contenido');

let s = raw.trim().replace(/```json\s*/gi,'').replace(/```/g,'').trim();
const tm = s.match(/<\/think>\s*([\s\S]*)/); if (tm) s = tm[1].trim();

let resultado;
try { resultado = JSON.parse(s); }
catch(e) {
  const m = s.match(/\{[\s\S]*\}/); if (!m) throw new Error('Sin JSON en Scout: '+s.substring(0,200));
  resultado = JSON.parse(m[0]);
}

const temas = resultado.temas_propuestos || resultado.temas || [];
if (!temas.length) throw new Error('Scout no extrajo temas: '+s.substring(0,300));

return temas.map(t => ({ json: t }));
'''

CODE_FILTRAR_NUEVOS = r'''
// Filtrar temas que ya existen en el Sheet para evitar duplicados
const temas_propuestos = $input.all().map(i => i.json);
const temas_existentes = $('Leer Temas Existentes').all().map(i => (i.json.tema||i.json.tema_nombre||'').toLowerCase().trim());

const temas_nuevos = temas_propuestos.filter(t => {
  const nombre = (t.tema_nombre || t.tema || '').toLowerCase().trim();
  if (!nombre) return false;
  // Verificar similitud básica (no exacta) para evitar duplicados semánticos
  return !temas_existentes.some(ex => {
    if (!ex) return false;
    // Dividir en palabras clave y ver si hay mucho solapamiento
    const palabras_nuevo = nombre.split(/\s+/).filter(p => p.length > 4);
    const solapamiento = palabras_nuevo.filter(p => ex.includes(p)).length;
    return solapamiento >= 2; // Si 2+ palabras clave coinciden, considerarlo duplicado
  });
});

if (temas_nuevos.length === 0) {
  return [{ json: { _sin_temas_nuevos: true, mensaje: 'Todos los temas propuestos ya existen en el Sheet' } }];
}

return temas_nuevos.map(t => ({ json: t }));
'''

CODE_PREP_APPEND = r'''
// Preparar fila para Google Sheets
const t = $json;
if (t._sin_temas_nuevos) return []; // Nada que agregar

const id = 'SCOUT-' + Date.now() + '-' + Math.random().toString(36).substring(2,6).toUpperCase();
return [{ json: {
  id,
  tema:              t.tema_nombre || t.tema || '',
  tema_nombre:       t.tema_nombre || t.tema || '',
  area:              t.area || 'diseño',
  tipo_post:         t.tipo_post || 'reflexión',
  nivel_profundidad: t.nivel_profundidad || 'avanzado',
  tono:              t.tono || 'directo',
  objetivo:          t.objetivo || 'posicionamiento',
  score:             t.score || '1.2',
  estado:            'disponible',
  fuente_scout:      t.fuente_scout || 'Scout Automático',
  fecha_scout:       new Date().toISOString().substring(0,10)
} }];
'''

CODE_PREP_NOTIF = r'''
const items = $input.all();
const temas_guardados = items.filter(i => !i.json._sin_temas_nuevos && i.json.tema_nombre);
const sin_nuevos = items.some(i => i.json._sin_temas_nuevos);

if (sin_nuevos || temas_guardados.length === 0) {
  return [{ json: {
    mensaje: '🤖 <b>[SCOUT] Sin temas nuevos</b>\n\nTodos los temas del día ya existen en el Sheet.'
  } }];
}

const lista = temas_guardados.slice(0,5).map((i,idx) => {
  const t = i.json;
  return `${idx+1}. <b>${(t.tema_nombre||'').substring(0,60)}</b> [${t.area}]`;
}).join('\n');

return [{ json: {
  mensaje: `🔍 <b>[SCOUT] ${temas_guardados.length} temas nuevos descubiertos</b>\n\n${lista}\n\nAgregados al Sheet Temas como "disponible".`
} }];
'''

# ─── PROMPTS ─────────────────────────────────────────────────────────

SYS_SCOUT = (
    "Eres el agente de inteligencia de contenido de Camilo Ayala Monje (@camiloayalam), "
    "comunicador y diseñador estratégico en Bogotá, Colombia.\n\n"
    "Tu trabajo: analizar artículos recientes de diseño, educación y comunicación estratégica "
    "y extraer ÁNGULOS DE POST únicos, no obvios y relevantes para la audiencia de Camilo.\n\n"
    "AUDIENCIA DE CAMILO: Diseñadores gráficos, directores creativos, CEOs, gerentes generales, "
    "community managers, fundadores. Líderes creativos en Colombia y Latam.\n\n"
    "CRITERIOS para un buen tema:\n"
    "- Genera una perspectiva que contradice una creencia común del sector\n"
    "- Conecta diseño/educación/comunicación con una tensión real del mercado colombiano/latinoamericano\n"
    "- Tiene una postura posible para Camilo basada en su experiencia docente o profesional\n"
    "- NO es genérico ni motivacional (nada de 'la importancia de la creatividad')\n"
    "- SÍ es específico, con ángulo de argumento claro\n\n"
    "Responde ÚNICAMENTE con JSON válido. Sin backticks, sin markdown, sin texto adicional."
)

PROMPT_SCOUT = (
    "Analiza estos artículos recientes y extrae 3 ángulos de tema para posts de LinkedIn de Camilo.\n\n"
    "ARTÍCULOS:\n{{ $json.texto_combinado }}\n\n"
    "Para cada tema, piensa: ¿qué afirmación no obvia puede hacer Camilo basándose en esto? "
    "¿Qué creencia común contradice? ¿Qué tensión real del mercado latinoamericano revela?\n\n"
    "Devuelve EXACTAMENTE este JSON (sin backticks):\n"
    '{"temas_propuestos":['
    '{"tema_nombre":"nombre específico del tema (no genérico, máximo 8 palabras)",'
    '"area":"diseño|educación|comunicación|marca_personal|liderazgo",'
    '"angulo":"la perspectiva no obvia o contradictoria que Camilo puede tomar",'
    '"tension":"la paradoja o contradicción que hace interesante el tema",'
    '"tipo_post":"reflexión|caso|datos|opinión|herramienta",'
    '"nivel_profundidad":"avanzado",'
    '"tono":"directo|reflexivo|provocador|analítico",'
    '"objetivo":"posicionamiento",'
    '"score":"1.5",'
    '"fuente_scout":"nombre del artículo fuente"},'
    '...2 temas más...]}'
)

# ─── BUILD ────────────────────────────────────────────────────────────

def build():
    nodes = []
    conn  = {}
    def add(n): nodes.append(n); return n

    # Triggers
    sched = add(n_schedule("Trigger Scout Diario",  "0 11 * * 1,3,5", [0, -200]))
    wh    = add(n_webhook ("Webhook Scout Manual",  "ma-scout-manual", [0, 200]))

    # Definir fuentes RSS
    src   = add(n_code("Definir Fuentes RSS",    CODE_RSS_SOURCES,   [260, 0]))

    # Fetch RSS (HTTP Request procesa todos los items del nodo anterior)
    fetch = add(n_http("Fetch RSS", "GET", "={{ $json.url }}", [520, 0]))

    # Parsear XML
    parse = add(n_code("Parsear Artículos RSS", CODE_PARSE_RSS,      [780, 0]))

    # Preparar URLs Jina
    jina_prep = add(n_code("Preparar URLs Jina",  CODE_PREP_JINA,    [1040, 0]))

    # Jina Reader — extrae texto limpio de cada URL
    jina_fetch = add(n_http("Jina Reader",
                            "GET", "={{ $json.jina_url }}", [1300, 0],
                            headers_extra={"Accept": "text/plain", "X-Return-Format": "text"}))

    # Combinar todos los textos
    comb = add(n_code("Combinar Artículos",      CODE_COMBINAR_ART,  [1560, 0]))

    # Qwen Scout — analiza y propone temas
    scout_llm = add(n_llm("🔍 Agente Scout Qwen",
                           SYS_SCOUT,
                           PROMPT_SCOUT,
                           0.6, 1500, [1820, 0]))

    # Parsear temas propuestos
    parsear   = add(n_code("Parsear Temas Scout",   CODE_PARSEAR_TEMAS,  [2080, 0]))

    # Leer temas existentes para filtrar duplicados
    leer_ex   = add(n_sheets_read("Leer Temas Existentes", "Temas", TEMAS_GID, [2080, 300]))

    # Filtrar nuevos
    filtrar   = add(n_code("Filtrar Temas Nuevos",  CODE_FILTRAR_NUEVOS, [2340, 0]))

    # Preparar datos para append
    prep_ap   = add(n_code("Preparar para Sheet",   CODE_PREP_APPEND,    [2600, 0]))

    # Guardar en Sheet
    save      = add(n_sheets_append("Guardar Temas Scout", TEMAS_GID, "Temas", {
        "id":               "={{ $json.id }}",
        "tema":             "={{ $json.tema }}",
        "tema_nombre":      "={{ $json.tema_nombre }}",
        "area":             "={{ $json.area }}",
        "tipo_post":        "={{ $json.tipo_post }}",
        "nivel_profundidad":"={{ $json.nivel_profundidad }}",
        "tono":             "={{ $json.tono }}",
        "objetivo":         "={{ $json.objetivo }}",
        "score":            "={{ $json.score }}",
        "estado":           "={{ $json.estado }}",
        "fuente_scout":     "={{ $json.fuente_scout }}",
        "fecha_scout":      "={{ $json.fecha_scout }}"
    }, [2860, 0]))

    # Preparar notificación
    prep_n = add(n_code("Preparar Notificación",    CODE_PREP_NOTIF,     [3120, 0]))

    # Notificar por Telegram
    tg     = add(n_tg("Telegram Scout ✅", CHAT_ID,
                      "={{ $json.mensaje }}", [3380, 0]))

    # ── CONEXIONES ─────────────────────────────────────────────────────
    for trigger in [sched["name"], wh["name"]]:
        connect(conn, trigger, src["name"])

    connect(conn, src["name"],       fetch["name"])
    connect(conn, fetch["name"],     parse["name"])
    connect(conn, parse["name"],     jina_prep["name"])
    connect(conn, jina_prep["name"], jina_fetch["name"])
    connect(conn, jina_fetch["name"],comb["name"])
    connect(conn, comb["name"],      scout_llm["name"])
    connect(conn, scout_llm["name"], parsear["name"])
    connect(conn, parsear["name"],   filtrar["name"])
    connect(conn, parsear["name"],   leer_ex["name"])   # leer en paralelo
    connect(conn, filtrar["name"],   prep_ap["name"])
    connect(conn, prep_ap["name"],   save["name"])
    connect(conn, save["name"],      prep_n["name"])
    connect(conn, prep_n["name"],    tg["name"])

    return {
        "name": "[MA] SCOUT — Descubridor de Temas",
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

if __name__ == "__main__":
    print("Construyendo [MA] SCOUT — Descubridor de Temas...")
    wf = build()
    print(f"  Nodos: {len(wf['nodes'])}")

    r = requests.post(f"{BASE_URL}/workflows", headers=HEADERS, json=wf, timeout=30)
    if r.status_code in (200, 201):
        d = r.json()
        wid = d.get("id","?")
        print(f"  ✅ SCOUT creado — ID: {wid}")
        print(f"  Webhook manual: https://n8n.camiloayala.net/webhook/ma-scout-manual")
        print(f"  UI: https://n8n.camiloayala.net/workflow/{wid}")
    else:
        print(f"  ❌ Error {r.status_code}: {r.text[:500]}")
