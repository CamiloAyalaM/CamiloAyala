#!/usr/bin/env python3
"""
[MA] FEEDBACK — Ciclo de Aprendizaje Semanal
Corre domingo a las 7 AM (o cuando ANALYST lo llama):
  1. Lee Temas + Metricas completos del Sheet
  2. Calcula correlaciones: ER por área / tono / tipo_post
  3. Qwen identifica patrones, genera recomendaciones estratégicas
  4. Actualiza scores globales de temas en función del rendimiento
  5. Envía informe semanal a Telegram
  6. Responde al webhook de ANALYST con los insights (si fue llamado)
"""
import json, uuid, requests

API_KEY  = "N8N_API_KEY_HERE"
BASE_URL = "https://n8n.camiloayala.net/api/v1"
HEADERS  = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}

SHEETS_ID    = "1TmHXCe_68qA8GDZhZfzK-qvOh0H09tZqAF3UI5nWSrI"
TEMAS_GID    = 1090471100
METRICAS_GID = 830260036
CHAT_ID      = "1160149765"
QWEN         = "qwen2.5:32b"
CRED_SHEETS  = {"id": "59A9Vs89LRQlZq9m", "name": "Google Sheets account"}
CRED_OLLAMA  = {"id": "S4LeOiFztrgDaMM9", "name": "Ollama"}
CRED_TG      = {"id": "gR2WcHsnoq4oIAuT", "name": "Telegram account"}

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
                "sheetName":  {"__rl": True, "value": gid, "mode": "list",
                               "cachedResultName": sheet_name},
                "options": {}
            },
            "credentials": {"googleSheetsOAuth2Api": CRED_SHEETS}}

def n_sheets_update(name, gid, sheet_name, cols_map, match_col, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.googleSheets",
            "typeVersion": 4.5, "position": pos,
            "parameters": {
                "operation": "update",
                "documentId": {"__rl": True, "value": SHEETS_ID, "mode": "id"},
                "sheetName":  {"__rl": True, "value": gid, "mode": "list",
                               "cachedResultName": sheet_name},
                "columns": {"mappingMode": "defineBelow", "value": cols_map,
                            "matchingColumns": [match_col], "schema": []},
                "options": {}
            },
            "credentials": {"googleSheetsOAuth2Api": CRED_SHEETS}}

def n_merge(name, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.merge",
            "typeVersion": 3, "position": pos,
            "parameters": {"mode": "combine", "combineBy": "combineAll", "options": {}}}

def n_tg(name, chat_id, text, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.telegram",
            "typeVersion": 1.2, "position": pos,
            "parameters": {"chatId": chat_id, "text": text,
                           "additionalFields": {"parse_mode": "HTML"}},
            "credentials": {"telegramApi": CRED_TG}}

def n_respond(name, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1, "position": pos,
            "parameters": {"respondWith": "json",
                           "responseBody": "={{ JSON.stringify($json) }}", "options": {}}}

def connect(conn, src, dst, out=0, inp=0):
    if src not in conn: conn[src] = {"main": []}
    while len(conn[src]["main"]) <= out: conn[src]["main"].append([])
    conn[src]["main"][out].append({"node": dst, "type": "main", "index": inp})

# ─── CÓDIGO NODES ─────────────────────────────────────────────────────

CODE_CALCULAR_CORRELACIONES = r'''
// Separar Temas y Métricas del Merge
const all = $input.all().map(i => i.json);
const temas    = all.filter(i => i.id && i.tema && !('engagement_rate' in i && 'post_id' in i));
const metricas = all.filter(i => i.post_id && ('engagement_rate' in i || 'likes' in i));

if (!metricas.length) {
  return [{ json: {
    texto_correlaciones: 'Sin datos de métricas históricos disponibles.',
    temas_pendientes: temas.filter(t => t.estado !== 'publicado').length,
    areas_res: [], tonos_res: [], tipos_res: [],
    er_global_avg: 0, er_mediana: 0,
    outliers_pos: [], outliers_neg: []
  }}];
}

// ── Correlaciones por dimensión ──
function calcResumen(map) {
  return Object.entries(map)
    .filter(([, ers]) => ers.length >= 1)
    .map(([key, ers]) => {
      const sorted = [...ers].sort((a, b) => a - b);
      const avg    = ers.reduce((a, b) => a + b, 0) / ers.length;
      const median = sorted[Math.floor(sorted.length / 2)];
      return { key, avg, median, count: ers.length, best: sorted[sorted.length - 1] };
    })
    .sort((a, b) => b.avg - a.avg);
}

const byArea = {}, byTono = {}, byTipo = {};
metricas.forEach(m => {
  const er = parseFloat(m.engagement_rate) || 0;
  // Only include posts with real data (er > 0)
  const area = (m.area || 'sin_area').toLowerCase();
  const tono = (m.tono || 'sin_tono').toLowerCase();
  const tipo = (m.tipo_post || 'sin_tipo').toLowerCase();
  if (!byArea[area]) byArea[area] = [];
  if (!byTono[tono]) byTono[tono] = [];
  if (!byTipo[tipo]) byTipo[tipo] = [];
  byArea[area].push(er);
  byTono[tono].push(er);
  byTipo[tipo].push(er);
});

const areas_res = calcResumen(byArea);
const tonos_res = calcResumen(byTono);
const tipos_res = calcResumen(byTipo);

// Global stats
const all_ers = metricas
  .map(m => parseFloat(m.engagement_rate) || 0)
  .filter(e => e > 0)
  .sort((a, b) => a - b);

const er_global_avg = all_ers.length
  ? all_ers.reduce((a, b) => a + b, 0) / all_ers.length
  : 0;
const er_mediana = all_ers.length ? all_ers[Math.floor(all_ers.length / 2)] : 0;

// Outliers
const outliers_pos = metricas
  .filter(m => parseFloat(m.engagement_rate) > er_mediana * 2 && er_mediana > 0)
  .sort((a, b) => parseFloat(b.engagement_rate) - parseFloat(a.engagement_rate))
  .slice(0, 5)
  .map(m => ({
    tema:            m.tema || m.area,
    area:            m.area,
    tono:            m.tono,
    tipo:            m.tipo_post,
    fecha:           m.fecha,
    er:              parseFloat(m.engagement_rate),
    ratio_mediana:   +(parseFloat(m.engagement_rate) / (er_mediana || 1)).toFixed(2)
  }));

const outliers_neg = metricas
  .filter(m => {
    const er = parseFloat(m.engagement_rate);
    return er > 0 && er < er_mediana * 0.35 && er_mediana > 0;
  })
  .slice(0, 3)
  .map(m => ({ tema: m.tema || m.area, area: m.area, er: parseFloat(m.engagement_rate) }));

// Build analysis text for Qwen
const fmt = (r) => `  ${r.key}: ER avg ${(r.avg * 100).toFixed(2)}%, mediana ${(r.median * 100).toFixed(2)}% (${r.count} posts)`;

const temas_pendientes = temas
  .filter(t => t.estado !== 'publicado')
  .slice(0, 12)
  .map(t => `  [${t.area || '?'}] ${t.tema || ''} | tono: ${t.tono || '?'} | score: ${t.score || '?'}`);

const texto_correlaciones = [
  `ANÁLISIS CORRELACIONES — ${metricas.length} posts | ${temas.length} temas`,
  `ER global: avg ${(er_global_avg * 100).toFixed(2)}%, mediana ${(er_mediana * 100).toFixed(2)}%`,
  ``,
  `RENDIMIENTO POR ÁREA (${areas_res.length} áreas):`,
  ...areas_res.slice(0, 8).map(fmt),
  ``,
  `RENDIMIENTO POR TONO (${tonos_res.length} tonos):`,
  ...tonos_res.slice(0, 6).map(fmt),
  ``,
  `RENDIMIENTO POR TIPO DE POST:`,
  ...tipos_res.slice(0, 5).map(fmt),
  ``,
  ...(outliers_pos.length > 0 ? [
    `POSTS ESTRELLA (ER > 2x mediana):`,
    ...outliers_pos.map(p => `  ★ ${p.tema} [${p.area}/${p.tono}]: ER ${(p.er * 100).toFixed(2)}% = ${p.ratio_mediana}x mediana`),
    ``
  ] : []),
  ...(outliers_neg.length > 0 ? [
    `POSTS CON BAJO RENDIMIENTO:`,
    ...outliers_neg.map(p => `  ↓ ${p.tema} [${p.area}]: ER ${(p.er * 100).toFixed(2)}%`),
    ``
  ] : []),
  `TEMAS PENDIENTES EN PIPELINE:`,
  ...temas_pendientes,
].join('\n');

return [{
  json: {
    texto_correlaciones:    texto_correlaciones.substring(0, 10000),
    areas_res,
    tonos_res,
    tipos_res,
    er_global_avg,
    er_mediana,
    outliers_pos,
    outliers_neg,
    temas_pendientes_count: temas.filter(t => t.estado !== 'publicado').length,
    total_metricas:         metricas.length
  }
}];
'''

CODE_PARSEAR_RECOMENDACIONES = r'''
const raw = $json.message?.content || $json.choices?.[0]?.message?.content || '';
if (!raw) {
  return [{ json: { ...$('Calcular Correlaciones').first().json, recom: null } }];
}
let s = raw.trim().replace(/```json\s*/gi, '').replace(/```/g, '').trim();
const tm = s.match(/<\/think>\s*([\s\S]*)/); if (tm) s = tm[1].trim();
let recom;
try { recom = JSON.parse(s); }
catch(e) { const m = s.match(/\{[\s\S]*\}/); recom = m ? JSON.parse(m[0]) : null; }
const prev = $('Calcular Correlaciones').first().json;
return [{ json: { ...prev, recom } }];
'''

CODE_CALCULAR_NUEVOS_SCORES = r'''
const data        = $json;
const recom       = data.recom || {};
const areas_res   = data.areas_res || [];
const tonos_res   = data.tonos_res || [];
const er_mediana  = data.er_mediana || 0;
const temas_sheet = $('Leer Temas Scores').all().map(i => i.json);

// Map de boost por área (normalizado 0.7 → 1.5)
const erPorArea = {};
areas_res.forEach(r => { erPorArea[r.key] = r.avg; });
const er_vals = areas_res.map(r => r.avg);
const er_max  = er_vals.length ? Math.max(...er_vals) : 1;
const er_min  = er_vals.length ? Math.min(...er_vals) : 0;
const rango   = er_max - er_min || 0.001;

function areaBoost(area) {
  const er = erPorArea[(area || '').toLowerCase()];
  if (er === undefined) return 1.0;
  return 0.7 + ((er - er_min) / rango) * 0.8;
}

// Areas/tonos que Qwen recomienda potenciar
const areas_boost = (recom?.ajustes?.areas_boost || []).map(a => a.toLowerCase());
const areas_pen   = (recom?.ajustes?.areas_penalizar || []).map(a => a.toLowerCase());
const tonos_boost = (recom?.ajustes?.tonos_boost || []).map(t => t.toLowerCase());

return temas_sheet
  .filter(t => t.id && t.estado !== 'publicado')
  .map(t => {
    const area  = (t.area  || '').toLowerCase();
    const tono  = (t.tono  || '').toLowerCase();
    let score   = parseFloat(t.score || '1.0');

    // Apply area performance factor
    score *= areaBoost(area);

    // Apply Qwen recommendations
    if (areas_boost.includes(area)) score *= 1.3;
    if (areas_pen.includes(area))   score *= 0.7;
    if (tonos_boost.includes(tono)) score *= 1.15;

    score = Math.min(Math.max(score, 0.2), 3.0);
    return { json: { id: t.id, score: score.toFixed(2) } };
  });
'''

CODE_PREP_INFORME_FEEDBACK = r'''
const data    = $json;
const recom   = data.recom || {};
const areas   = (data.areas_res || []).slice(0, 5);
const tonos   = (data.tonos_res || []).slice(0, 4);
const out_pos = (data.outliers_pos || []).slice(0, 3);
const total   = data.total_metricas || 0;
const pendientes = data.temas_pendientes_count || 0;

const conclusion = recom?.conclusiones || {};
const proximas   = recom?.proximas_semanas || {};
const alerta     = recom?.alerta || '';

const areas_html = areas.map(r =>
  `  • <b>${r.key}</b>: ER avg ${(r.avg * 100).toFixed(2)}%, mediana ${(r.median * 100).toFixed(2)}% (${r.count} posts)`
).join('\n');

const tonos_html = tonos.map(r =>
  `  • ${r.key}: ${(r.avg * 100).toFixed(2)}% avg (${r.count} posts)`
).join('\n');

const out_html = out_pos.length
  ? out_pos.map(p => `  🌟 ${p.tema} [${p.area}/${p.tono}]: ${(p.er * 100).toFixed(2)}% ER`).join('\n')
  : '  (ninguno con datos suficientes)';

const msg = [
  `🔄 <b>[FEEDBACK] Ciclo de Aprendizaje Semanal</b>`,
  ``,
  `Posts analizados: ${total} | Temas pendientes: ${pendientes}`,
  ``,
  `<b>Rendimiento por área:</b>`,
  areas_html || '  (sin datos)',
  ``,
  `<b>Rendimiento por tono:</b>`,
  tonos_html || '  (sin datos)',
  ``,
  `<b>Posts estrella de la semana:</b>`,
  out_html,
  ``,
  ...(conclusion.area_estrella ? [
    `<b>Área estrella:</b> ${conclusion.area_estrella}`,
    `<b>Tono ganador:</b> ${conclusion.tono_ganador || '?'}`,
    `<b>Día óptimo:</b> ${conclusion.dia_optimo || '?'}`,
    ``,
    `<b>Patrón principal:</b>`,
    conclusion.patron_principal || '...',
    ``
  ] : []),
  ...(proximas.enfoque ? [
    `<b>Enfoque próxima semana:</b> ${proximas.enfoque}`,
    ...(proximas.evitar ? [`<b>Evitar:</b> ${proximas.evitar}`] : []),
    ``
  ] : []),
  ...(alerta ? [`⚠️ <b>Alerta:</b> ${alerta}`, ``] : []),
  `Scores actualizados en Sheet ✅`
].join('\n');

return [{ json: { mensaje: msg, recom, areas_res: areas, tonos_res: tonos } }];
'''

# ─── PROMPTS ─────────────────────────────────────────────────────────

SYS_FEEDBACK = (
    "Eres el agente de aprendizaje continuo del sistema de contenido de Camilo Ayala Monje. "
    "Analizas correlaciones históricas de engagement en LinkedIn para optimizar la estrategia. "
    "Piensas en patrones, no en posts individuales.\n\n"
    "Responde ÚNICAMENTE con JSON válido. Sin backticks, sin markdown, sin texto adicional."
)

PROMPT_FEEDBACK = (
    "Analiza estas correlaciones históricas de LinkedIn de Camilo Ayala "
    "y genera una estrategia accionable para el próximo ciclo de contenido.\n\n"
    "{{ $json.texto_correlaciones }}\n\n"
    "Devuelve exactamente este JSON (sin backticks):\n"
    '{"conclusiones":{'
    '"area_estrella":"el área con mejor ER consistente",'
    '"tono_ganador":"el tono que más consistentemente funciona",'
    '"dia_optimo":"si hay patrón de día, sino null",'
    '"patron_principal":"el patrón más significativo en 1-2 oraciones concretas"},'
    '"ajustes":{'
    '"areas_boost":["áreas a priorizar esta semana (exactamente como aparecen en datos)"],'
    '"areas_penalizar":["áreas a reducir temporalmente"],'
    '"tonos_boost":["tonos a usar más"],'
    '"explicacion":"por qué estos ajustes (1 oración)"},'
    '"proximas_semanas":{'
    '"enfoque":"en qué área y tono enfocarse (específico)",'
    '"evitar":"qué evitar la próxima semana"},'
    '"alerta":"si hay tendencia preocupante o oportunidad urgente, sino vacío"}'
)

# ─── BUILD ────────────────────────────────────────────────────────────

def build():
    nodes = []
    conn  = {}
    def add(n): nodes.append(n); return n

    # Triggers: semanal + manual + llamado por ANALYST
    sched  = add(n_schedule("Trigger Semanal FEEDBACK", "0 7 * * 0", [0, -200]))  # Domingo 7AM
    wh     = add(n_webhook ("Webhook FEEDBACK Manual", "ma-feedback-manual", [0, 200]))

    # Leer datos en paralelo
    leer_t = add(n_sheets_read("Leer Temas Feedback",   "Temas",    TEMAS_GID,    [260, -200]))
    leer_m = add(n_sheets_read("Leer Metricas Feedback","Metricas", METRICAS_GID, [260,  200]))
    merge  = add(n_merge("Merge Temas + Metricas", [520, 0]))

    # Calcular correlaciones
    calc   = add(n_code("Calcular Correlaciones", CODE_CALCULAR_CORRELACIONES, [780, 0]))

    # Qwen análisis de patrones
    qwen   = add(n_llm("🔄 Agente FEEDBACK Qwen",
                        SYS_FEEDBACK, PROMPT_FEEDBACK, 0.3, 1800, [1040, 0]))
    parsear= add(n_code("Parsear Recomendaciones", CODE_PARSEAR_RECOMENDACIONES, [1300, 0]))

    # Actualizar scores globales
    leer_ts= add(n_sheets_read("Leer Temas Scores", "Temas", TEMAS_GID, [1300, 300]))
    act_sc = add(n_code("Calcular Nuevos Scores", CODE_CALCULAR_NUEVOS_SCORES, [1560, 0]))
    upd_sc = add(n_sheets_update("Update Scores FEEDBACK", TEMAS_GID, "Temas", {
        "id":    "={{ $json.id }}",
        "score": "={{ $json.score }}"
    }, "id", [1820, 0]))

    # Informe + respuesta webhook + Telegram
    prep_inf= add(n_code("Preparar Informe Feedback", CODE_PREP_INFORME_FEEDBACK, [2080, 0]))
    respond = add(n_respond("Responder Webhook", [2340, -200]))
    tg_rep  = add(n_tg("Telegram Informe Semanal 🔄", CHAT_ID, "={{ $json.mensaje }}", [2340, 200]))

    # ── CONEXIONES ─────────────────────────────────────────────────────
    for trigger in [sched["name"], wh["name"]]:
        connect(conn, trigger, leer_t["name"])
        connect(conn, trigger, leer_m["name"])

    connect(conn, leer_t["name"], merge["name"], inp=0)
    connect(conn, leer_m["name"], merge["name"], inp=1)

    connect(conn, merge["name"],  calc["name"])
    connect(conn, calc["name"],   qwen["name"])
    connect(conn, qwen["name"],   parsear["name"])

    # Sequential: parsear → leer temas → calcular → actualizar scores
    connect(conn, parsear["name"], leer_ts["name"])
    connect(conn, leer_ts["name"], act_sc["name"])
    connect(conn, act_sc["name"],  upd_sc["name"])
    connect(conn, upd_sc["name"],  prep_inf["name"])

    # Bifurcación final: responder webhook + Telegram en paralelo
    connect(conn, prep_inf["name"], respond["name"])
    connect(conn, prep_inf["name"], tg_rep["name"])

    return {
        "name": "[MA] FEEDBACK — Ciclo de Aprendizaje",
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
    print("Construyendo [MA] FEEDBACK — Ciclo de Aprendizaje...")
    wf = build()
    print(f"  Nodos: {len(wf['nodes'])}")
    print(f"  Conexiones src: {len(wf['connections'])}")

    r = requests.post(f"{BASE_URL}/workflows", headers=HEADERS, json=wf, timeout=30)
    if r.status_code in (200, 201):
        d   = r.json()
        wid = d.get("id", "?")
        print(f"  ✅ FEEDBACK creado — ID: {wid}")
        print(f"  Webhook: https://n8n.camiloayala.net/webhook/ma-feedback-manual")
        print(f"  UI: https://n8n.camiloayala.net/workflow/{wid}")
        ra = requests.post(f"{BASE_URL}/workflows/{wid}/activate", headers=HEADERS, timeout=10)
        print(f"  Activar: {ra.status_code}")
    else:
        print(f"  ❌ Error {r.status_code}: {r.text[:600]}")
