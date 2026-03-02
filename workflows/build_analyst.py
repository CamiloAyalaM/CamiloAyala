#!/usr/bin/env python3
"""
[MA] ANALYST — Métricas y Feedback Loop
Corre diariamente a las 8 PM:
  1. Lee posts publicados del Sheet
  2. Lanza Apify scraper de LinkedIn
  3. Procesa métricas (ER, likes, comentarios)
  4. Qwen analiza patrones: qué temas/tonos generan más engagement
  5. Actualiza scores de temas en Sheet
  6. Envía informe por Telegram
"""
import json, uuid, requests

API_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0YmY4ODRkNC1hMGUxLTRiNjgtOTVlZC1kMDc0ZWY5N2ExZDQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOWY0MWY5OWQtZDNkNy00NWNjLWFkZjAtZjc2ZmMwZDQxZjcyIiwiaWF0IjoxNzcxNzcyMzg4fQ.RmQl5yX4T9pAUn4swhvMcydMv-8VukNnlbPc7NgbK0U"
BASE_URL = "https://n8n.camiloayala.net/api/v1"
HEADERS  = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}

SHEETS_ID    = "1TmHXCe_68qA8GDZhZfzK-qvOh0H09tZqAF3UI5nWSrI"
TEMAS_GID    = 1090471100
METRICAS_GID = 830260036
CHAT_ID      = "1160149765"
APIFY_TOKEN  = "APIFY_TOKEN_HERE  # set via N8N credential or env"
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

def n_http_body(name, method, url, pos, body_json, headers_extra=None):
    p = {"method": method.upper(), "url": url, "sendBody": True,
         "specifyBody": "json",
         "jsonBody": body_json if isinstance(body_json, str) else json.dumps(body_json),
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

def n_sheets_update(name, gid, sheet_name, cols_map, match_col, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.googleSheets",
            "typeVersion": 4.5, "position": pos,
            "parameters": {
                "operation": "update",
                "documentId": {"__rl": True, "value": SHEETS_ID, "mode": "id"},
                "sheetName": {"__rl": True, "value": gid, "mode": "list",
                              "cachedResultName": sheet_name},
                "columns": {"mappingMode": "defineBelow", "value": cols_map,
                            "matchingColumns": [match_col], "schema": []},
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

CODE_FILTRAR_POSTS = r'''
// Filtrar posts publicados que tienen post_id y tienen menos de 30 días
const items = $input.all();
const ahora = Date.now();
const limite30d = ahora - (30 * 24 * 60 * 60 * 1000);

const posts_a_actualizar = items
  .map(i => i.json)
  .filter(r => {
    if (!r.post_id || r.estado !== 'publicado') return false;
    if (r.fecha_pub) {
      const fp = new Date(r.fecha_pub).getTime();
      return fp > limite30d; // Solo posts de los últimos 30 días
    }
    return true;
  })
  .slice(0, 20); // Máximo 20 posts por ejecución

if (posts_a_actualizar.length === 0) {
  return [{ json: { _sin_posts: true, mensaje: 'No hay posts publicados recientes para analizar' } }];
}

// Pasar como un solo item con array de URLs
const urls = posts_a_actualizar.map(p => `https://www.linkedin.com/feed/update/${p.post_id}/`).filter(Boolean);
return [{ json: { posts: posts_a_actualizar, urls_linkedin: urls, count: posts_a_actualizar.length } }];
'''

CODE_PREP_APIFY = '''
const data = $json;
if (data._sin_posts) return [{ json: data }];

return [{ json: {
  profileUrls: ["https://www.linkedin.com/in/camiloayalam/"],
  profilePublicIdentifiers: ["camiloayalam"],
  count: 25
} }];
'''

CODE_PROCESAR_METRICAS = r'''
const apify_raw = $json;
const posts_meta = $('Filtrar Posts a Actualizar').first().json.posts || [];

// Construir mapa de post_id → metadata del sheet
const metaMap = {};
posts_meta.forEach(p => {
  if (p.post_id) metaMap[p.post_id] = p;
});

// Procesar respuesta de Apify
const items_apify = Array.isArray(apify_raw) ? apify_raw : (apify_raw.items || apify_raw.data || []);

const metricas = items_apify.map(post => {
  const post_id = post.id || post.postId || post.entityUrn || '';
  const likes   = parseInt(post.reactions?.count || post.likeCount || post.numLikes || 0);
  const comments= parseInt(post.commentsCount || post.numComments || 0);
  const reposts = parseInt(post.repostsCount || post.numReposts || 0);
  const views   = parseInt(post.impressionCount || post.numImpressions || 0);
  const connections = 5065; // Conexiones reales de Camilo
  const er = views > 0 ? (likes + comments*2 + reposts*3) / views : (likes + comments*2 + reposts*3) / connections;
  const meta = metaMap[post_id] || {};

  return {
    post_id,
    area:             meta.area || post.area || 'general',
    tema:             meta.tema || meta.tema_nombre || '',
    tipo_post:        meta.tipo_post || '',
    tono:             meta.tono || '',
    fecha:            post.date || post.postedDate || meta.fecha_pub || '',
    likes,
    comments,
    reposts,
    views,
    engagement_rate:  Math.round(er * 10000) / 10000,
    er_percent:       (er * 100).toFixed(3) + '%'
  };
}).filter(m => m.post_id);

if (!metricas.length) {
  return [{ json: { _sin_metricas: true, mensaje: 'Apify no devolvió posts con métricas' } }];
}

// Calcular promedios por área
const erPorArea = {};
metricas.forEach(m => {
  const a = m.area || 'general';
  if (!erPorArea[a]) erPorArea[a] = { sum: 0, count: 0, ers: [] };
  erPorArea[a].sum += m.engagement_rate;
  erPorArea[a].count++;
  erPorArea[a].ers.push(m.engagement_rate);
});

const resumen_areas = Object.entries(erPorArea).map(([area, data]) => ({
  area,
  er_promedio: (data.sum / data.count).toFixed(4),
  posts_count: data.count
})).sort((a,b) => parseFloat(b.er_promedio) - parseFloat(a.er_promedio));

return [{ json: { metricas, resumen_areas, total_posts: metricas.length } }];
'''

CODE_PREP_METRICAS_APPEND = r'''
const data = $json;
if (data._sin_metricas) return [];
const metricas = data.metricas || [];
return metricas.map(m => ({ json: m }));
'''

CODE_PREP_ANALYSIS = r'''
const data = $json;
if (data._sin_metricas) return [{ json: data }];

const metricas = data.metricas || [];
const resumen  = data.resumen_areas || [];

// Calcular estadísticas globales
const ers = metricas.map(m => m.engagement_rate).filter(e => e > 0).sort((a,b) => a-b);
const er_median = ers.length ? ers[Math.floor(ers.length/2)] : 0;
const er_top25  = ers.length ? ers[Math.floor(ers.length*0.75)] : 0;

// Top posts
const top_posts = [...metricas]
  .sort((a,b) => b.engagement_rate - a.engagement_rate)
  .slice(0,5)
  .map(p => `- ${p.tema||p.area}: ER=${(p.engagement_rate*100).toFixed(2)}% (${p.likes}♥ ${p.comments}💬)`);

// Preparar texto para Qwen
const texto_analisis = [
  `MÉTRICAS DE ${metricas.length} POSTS (últimos 30 días):`,
  ``,
  `ER mediana: ${(er_median*100).toFixed(3)}%`,
  `ER top 25%: ${(er_top25*100).toFixed(3)}%`,
  ``,
  `RENDIMIENTO POR ÁREA:`,
  ...resumen.map(r => `- ${r.area}: ER promedio ${(parseFloat(r.er_promedio)*100).toFixed(2)}% (${r.posts_count} posts)`),
  ``,
  `TOP 5 POSTS POR ER:`,
  ...top_posts,
  ``,
  `DETALLE DE MÉTRICAS:`,
  ...metricas.map(m => `${m.fecha||'?'} | ${m.area} | ${m.tono||'?'} | ER=${(m.engagement_rate*100).toFixed(2)}% | ${m.likes}♥ ${m.comments}💬 ${m.views}👁`)
].join('\n');

return [{ json: { ...data, texto_analisis: texto_analisis.substring(0, 8000) } }];
'''

CODE_PARSEAR_INSIGHTS = r'''
const raw = $json.message?.content || $json.choices?.[0]?.message?.content || '';
if (!raw) {
  // Si Qwen falla, usar análisis básico directo
  return [{ json: { insights: null, usar_basico: true } }];
}
let s = raw.trim().replace(/```json\s*/gi,'').replace(/```/g,'').trim();
const tm = s.match(/<\/think>\s*([\s\S]*)/); if (tm) s = tm[1].trim();
let ins;
try { ins = JSON.parse(s); }
catch(e) { const m=s.match(/\{[\s\S]*\}/); ins = m ? JSON.parse(m[0]) : null; }
const data_prev = $('Preparar Texto Análisis').first().json;
return [{ json: { ...data_prev, insights: ins } }];
'''

CODE_ACTUALIZAR_SCORES = r'''
// Actualizar scores de temas basándose en el rendimiento histórico del área
const data = $json;
const insights = data.insights || {};
const resumen = data.resumen_areas || [];
const temas_sheet = $('Leer Temas para Scores').all().map(i => i.json);

// Crear mapa de boost por área basado en ER real
const boostPorArea = {};
if (resumen.length > 0) {
  const er_max = Math.max(...resumen.map(r => parseFloat(r.er_promedio)));
  const er_min = Math.min(...resumen.map(r => parseFloat(r.er_promedio)));
  const rango = er_max - er_min || 0.001;
  resumen.forEach(r => {
    const er = parseFloat(r.er_promedio);
    // Normalizar entre 0.8 (bajo) y 1.4 (alto)
    boostPorArea[r.area] = 0.8 + ((er - er_min) / rango) * 0.6;
  });
}

// Sugerencias de temas del insights de Qwen
const temas_sugeridos = insights?.temas_a_reforzar || [];
const areas_top       = insights?.areas_top?.map(a => a.toLowerCase()) || [];

const temas_actualizados = temas_sheet
  .filter(t => t.id && t.estado !== 'publicado')
  .map(t => {
    const area = (t.area || '').toLowerCase();
    const boost = boostPorArea[area] || 1.0;
    const score_actual = parseFloat(t.score || '1.0');
    // Aplicar boost del área con suavizado
    const score_nuevo = Math.round(score_actual * (0.7 + boost * 0.3) * 100) / 100;
    // Boost extra si el área está en el top de Qwen
    const score_final = areas_top.includes(area) ? Math.min(score_nuevo * 1.2, 3.0) : Math.min(score_nuevo, 2.5);
    return { id: t.id, score: score_final.toFixed(2), area };
  });

return temas_actualizados.map(t => ({ json: t }));
'''

CODE_PREP_INFORME = r'''
const data = $('Parsear Insights Qwen').first().json || {};
const ins  = data.insights || {};
const res  = data.resumen_areas || [];
const total = data.total_posts || 0;

const areas_html = res.slice(0,5).map(r =>
  `  • <b>${r.area}</b>: ER ${(parseFloat(r.er_promedio)*100).toFixed(2)}% (${r.posts_count} posts)`
).join('\n');

const rec = (ins?.recomendaciones_tono || []).slice(0,3).join('\n  • ') || 'Sin recomendaciones aún';
const areas_top = (ins?.areas_top || []).join(', ') || 'datos insuficientes';

const msg = [
  `📊 <b>[ANALYST] Informe Diario de Engagement</b>`,
  ``,
  `Posts analizados: ${total}`,
  ``,
  `<b>ER por área:</b>`,
  areas_html || '  (sin datos)' ,
  ``,
  `<b>Áreas de mayor tracción:</b> ${areas_top}`,
  ``,
  `<b>Recomendaciones de tono:</b>`,
  `  • ${rec}`,
  ``,
  `Scores de temas actualizados en el Sheet ✅`
].join('\n');

return [{ json: { mensaje: msg } }];
'''

# ─── PROMPTS ─────────────────────────────────────────────────────────

SYS_ANALYST = (
    "Eres el agente de análisis de contenido de Camilo Ayala Monje. "
    "Analizas métricas de engagement de LinkedIn para identificar patrones y optimizar la estrategia de contenido.\n\n"
    "Responde ÚNICAMENTE con JSON válido. Sin backticks, sin markdown, sin texto adicional."
)

PROMPT_ANALYST = (
    "Analiza estas métricas de LinkedIn de Camilo Ayala y extrae insights accionables.\n\n"
    "{{ $json.texto_analisis }}\n\n"
    "Devuelve exactamente este JSON (sin backticks):\n"
    '{"areas_top":["lista de 2-3 áreas con mejor ER"],'
    '"areas_bajas":["lista de 1-2 áreas con ER bajo"],'
    '"tonos_efectivos":["lista de tonos que correlacionan con mejor ER"],'
    '"hora_optima":"observación sobre timing si aplica",'
    '"patron_detectado":"el patrón más significativo encontrado en los datos (1-2 oraciones)",'
    '"recomendaciones_tono":["recomendación 1 para próximos posts","recomendación 2","recomendación 3"],'
    '"temas_a_reforzar":["tema o área a priorizar esta semana"],'
    '"alerta":"si hay algo preocupante en las métricas, sino vacío"}'
)

# ─── BUILD ────────────────────────────────────────────────────────────

def build():
    nodes = []
    conn  = {}
    def add(n): nodes.append(n); return n

    sched  = add(n_schedule("Trigger Analyst Diario", "0 23 * * 1,3,5", [0, -200]))
    wh     = add(n_webhook ("Webhook Analyst Manual", "ma-analyst-manual", [0, 200]))

    # Leer datos
    leer_t = add(n_sheets_read("Leer Temas Sheet",  "Temas",    TEMAS_GID,    [260, 0]))
    leer_m = add(n_sheets_read("Leer Metricas Sheet","Metricas", METRICAS_GID, [260, 300]))

    filtrar = add(n_code("Filtrar Posts a Actualizar", CODE_FILTRAR_POSTS, [520, 0]))

    # Preparar y lanzar Apify
    prep_ap = add(n_code("Preparar Body Apify", CODE_PREP_APIFY, [780, 0]))
    apify   = add(n_http_body("Lanzar Apify Scraper", "POST",
        f"https://api.apify.com/v2/acts/harvestapi~linkedin-profile-posts/run-sync-get-dataset-items?token={APIFY_TOKEN}",
        [1040, 0],
        body_json=json.dumps({
            "profileUrls": ["https://www.linkedin.com/in/camiloayalam/"],
            "profilePublicIdentifiers": ["camiloayalam"],
            "count": 25
        }),
        headers_extra={"Content-Type": "application/json"}
    ))

    # Procesar métricas
    proc_m  = add(n_code("Procesar Métricas",    CODE_PROCESAR_METRICAS,  [1300, 0]))
    prep_ap2= add(n_code("Preparar para Append", CODE_PREP_METRICAS_APPEND,[1560, 0]))

    # Guardar métricas en Sheet
    save_m  = add(n_sheets_append("Guardar Métricas", METRICAS_GID, "Metricas", {
        "post_id":          "={{ $json.post_id }}",
        "area":             "={{ $json.area }}",
        "tema":             "={{ $json.tema }}",
        "tipo_post":        "={{ $json.tipo_post }}",
        "tono":             "={{ $json.tono }}",
        "fecha":            "={{ $json.fecha }}",
        "likes":            "={{ $json.likes }}",
        "comments":         "={{ $json.comments }}",
        "reposts":          "={{ $json.reposts }}",
        "views":            "={{ $json.views }}",
        "engagement_rate":  "={{ $json.engagement_rate }}"
    }, [1820, 0]))

    # Análisis con Qwen
    prep_txt = add(n_code("Preparar Texto Análisis", CODE_PREP_ANALYSIS,   [2080, 0]))
    qwen_ins = add(n_llm("🧠 Agente Analyst Qwen",
                          SYS_ANALYST, PROMPT_ANALYST, 0.3, 1200, [2340, 0]))
    pars_ins = add(n_code("Parsear Insights Qwen",  CODE_PARSEAR_INSIGHTS, [2600, 0]))

    # Leer temas para actualizar scores
    leer_ts  = add(n_sheets_read("Leer Temas para Scores", "Temas", TEMAS_GID, [2600, 300]))
    act_sc   = add(n_code("Actualizar Scores Temas", CODE_ACTUALIZAR_SCORES, [2860, 0]))
    upd_sc   = add(n_sheets_update("Update Scores Sheet", TEMAS_GID, "Temas", {
        "id":    "={{ $json.id }}",
        "score": "={{ $json.score }}"
    }, "id", [3120, 0]))

    # Informe Telegram
    prep_inf = add(n_code("Preparar Informe",   CODE_PREP_INFORME, [3380, 0]))
    tg_inf   = add(n_tg  ("Telegram Informe 📊", CHAT_ID, "={{ $json.mensaje }}", [3640, 0]))

    # ── CONEXIONES ─────────────────────────────────────────────────────
    for trigger in [sched["name"], wh["name"]]:
        connect(conn, trigger, leer_t["name"])
        connect(conn, trigger, leer_m["name"])

    connect(conn, leer_t["name"],   filtrar["name"])
    connect(conn, filtrar["name"],  prep_ap["name"])
    connect(conn, prep_ap["name"],  apify["name"])
    connect(conn, apify["name"],    proc_m["name"])
    connect(conn, proc_m["name"],   prep_ap2["name"])
    connect(conn, prep_ap2["name"], save_m["name"])
    connect(conn, save_m["name"],   prep_txt["name"])
    connect(conn, prep_txt["name"], qwen_ins["name"])
    connect(conn, qwen_ins["name"], pars_ins["name"])
    connect(conn, pars_ins["name"], leer_ts["name"])
    connect(conn, pars_ins["name"], act_sc["name"])
    connect(conn, act_sc["name"],   upd_sc["name"])
    connect(conn, upd_sc["name"],   prep_inf["name"])
    connect(conn, prep_inf["name"], tg_inf["name"])

    return {
        "name": "[MA] ANALYST — Métricas y Feedback",
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
    print("Construyendo [MA] ANALYST — Métricas y Feedback...")
    wf = build()
    print(f"  Nodos: {len(wf['nodes'])}")

    r = requests.post(f"{BASE_URL}/workflows", headers=HEADERS, json=wf, timeout=30)
    if r.status_code in (200, 201):
        d = r.json()
        wid = d.get("id","?")
        print(f"  ✅ ANALYST creado — ID: {wid}")
        print(f"  Webhook manual: https://n8n.camiloayala.net/webhook/ma-analyst-manual")
        print(f"  UI: https://n8n.camiloayala.net/workflow/{wid}")
    else:
        print(f"  ❌ Error {r.status_code}: {r.text[:500]}")
