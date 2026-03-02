#!/usr/bin/env python3
"""
update_analyst_v2.py
Actualiza [MA] ANALYST — reemplaza Apify con LinkedIn API nativa (cero costo).
  - Elimina nodos Apify (POST de pago)
  - Agrega GET a LinkedIn ugcPosts API (Bearer token ya existente)
  - Usa datos históricos del Sheet como fallback de métricas
  - Agrega detección de outliers con notificación Telegram
  - Agrega llamada al webhook de FEEDBACK al final del ciclo
"""
import json, uuid, requests

API_KEY     = "N8N_API_KEY_HERE"
BASE_URL    = "https://n8n.camiloayala.net/api/v1"
HEADERS     = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}
ANALYST_ID  = "cwAt7hnhFF8xY7Cn"
WRITER_ID   = "p71hf2LpPVg7vcSO"
SHEETS_ID   = "1TmHXCe_68qA8GDZhZfzK-qvOh0H09tZqAF3UI5nWSrI"
TEMAS_GID   = 1090471100
METRICAS_GID= 830260036
CHAT_ID     = "1160149765"
QWEN        = "qwen2.5:32b"
LINKEDIN_AUTHOR_ENC = "urn%3Ali%3Aperson%3AjAuei1KlC1"
FEEDBACK_WH = "https://n8n.camiloayala.net/webhook/ma-feedback-manual"
CRED_SHEETS = {"id": "59A9Vs89LRQlZq9m", "name": "Google Sheets account"}
CRED_OLLAMA = {"id": "S4LeOiFztrgDaMM9", "name": "Ollama"}
CRED_TG     = {"id": "gR2WcHsnoq4oIAuT", "name": "Telegram account"}

def nid(): return str(uuid.uuid4())

# ── Extract LinkedIn token from already-deployed WRITER (avoids hardcoding) ──
def get_linkedin_token():
    try:
        r = requests.get(f"{BASE_URL}/workflows/{WRITER_ID}", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return "LINKEDIN_BEARER_TOKEN_HERE"
        for node in r.json().get("nodes", []):
            if node.get("name") == "Publicar LinkedIn":
                for h in node.get("parameters", {}).get("headerParameters", {}).get("parameters", []):
                    if h.get("name") == "Authorization":
                        return h.get("value", "").replace("Bearer ", "").strip()
    except Exception:
        pass
    return "LINKEDIN_BEARER_TOKEN_HERE"

LINKEDIN_TOKEN = get_linkedin_token()
print(f"  LinkedIn token: {'OK (extraído de WRITER)' if LINKEDIN_TOKEN != 'LINKEDIN_BEARER_TOKEN_HERE' else 'PLACEHOLDER'}")

# ─── NODE BUILDERS ────────────────────────────────────────────────────

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

def n_http_get(name, url, pos, headers_extra=None):
    p = {"method": "GET", "url": url,
         "options": {"response": {"response": {"neverError": True}}}}
    if headers_extra:
        p["sendHeaders"] = True
        p["headerParameters"] = {"parameters": [{"name": k, "value": v}
                                                  for k, v in headers_extra.items()]}
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2, "position": pos, "parameters": p}

def n_http_post(name, url, pos, body_json=None):
    p = {"method": "POST", "url": url,
         "options": {"response": {"response": {"neverError": True}}}}
    if body_json is not None:
        p["sendBody"] = True
        p["specifyBody"] = "json"
        p["jsonBody"] = body_json if isinstance(body_json, str) else json.dumps(body_json)
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
// Filtrar posts publicados que tienen post_id y tienen menos de 45 días
const items = $input.all();
const ahora = Date.now();
const limite45d = ahora - (45 * 24 * 60 * 60 * 1000);

const posts_a_analizar = items
  .map(i => i.json)
  .filter(r => {
    if (!r.post_id || r.estado !== 'publicado') return false;
    if (r.fecha_pub) {
      const fp = new Date(r.fecha_pub).getTime();
      return fp > limite45d;
    }
    return true;
  })
  .slice(0, 25);

if (posts_a_analizar.length === 0) {
  return [{ json: { _sin_posts: true, mensaje: 'No hay posts publicados recientes para analizar' } }];
}

return [{ json: { posts: posts_a_analizar, count: posts_a_analizar.length } }];
'''

# LinkedIn API: fetch own ugcPosts — free, uses existing Bearer token
# projection includes stats fields (available with w_member_social scope)
LI_URL = (
    f"https://api.linkedin.com/v2/ugcPosts"
    f"?q=authors&authors=List({LINKEDIN_AUTHOR_ENC})&count=25"
    f"&projection=(elements*(id,firstPublishedAt,specificContent,likesSummary,commentsSummary,totalShareStatistics))"
)

CODE_PROCESAR_METRICAS = r'''
// Procesar métricas: combina respuesta LinkedIn API + datos históricos del Sheet
const li_resp   = $json;
const posts_meta = $('Filtrar Posts a Actualizar').first().json.posts || [];
// Historical metrics from the Metricas sheet (run in parallel from trigger)
const metricas_hist = $('Leer Metricas Sheet').all().map(i => i.json);

// Build historical map: post_id → last known engagement
const histMap = {};
metricas_hist.forEach(m => {
  if (!m.post_id) return;
  const er = parseFloat(m.engagement_rate) || 0;
  if (!histMap[m.post_id] || er > (histMap[m.post_id].engagement_rate || 0)) {
    histMap[m.post_id] = {
      likes:           parseInt(m.likes)    || 0,
      comments:        parseInt(m.comments) || 0,
      reposts:         parseInt(m.reposts)  || 0,
      views:           parseInt(m.views)    || 0,
      engagement_rate: er
    };
  }
});

// Build map from LinkedIn API response
const liMap = {};
const li_elements = li_resp.elements || li_resp.data?.elements || [];
li_elements.forEach(elem => {
  if (!elem.id) return;
  liMap[elem.id] = {
    likes:    elem.likesSummary?.aggregatedCounts?.numLikes    || 0,
    comments: elem.commentsSummary?.aggregatedCounts?.numComments || 0,
    reposts:  elem.totalShareStatistics?.shareCount             || 0,
    views:    elem.totalShareStatistics?.impressionCount        || 0,
  };
});

const CONNECTIONS = 5065;

const metricas = posts_meta.map(post => {
  const pid = post.post_id;
  const li  = liMap[pid] || {};
  const hist= histMap[pid] || {};

  // LinkedIn API data has priority; fallback to historical sheet data
  const likes    = li.likes    > 0 ? li.likes    : (hist.likes    || 0);
  const comments = li.comments > 0 ? li.comments : (hist.comments || 0);
  const reposts  = li.reposts  > 0 ? li.reposts  : (hist.reposts  || 0);
  const views    = li.views    > 0 ? li.views    : (hist.views    || 0);

  const er_num = views > 0
    ? (likes + comments * 2 + reposts * 3) / views
    : (likes + comments * 2 + reposts * 3) / CONNECTIONS;

  const fuente = li.likes > 0 || li.comments > 0
    ? 'linkedin_api'
    : hist.engagement_rate > 0 ? 'sheet_historico' : 'sin_datos';

  return {
    post_id:         pid,
    area:            post.area       || 'general',
    tema:            post.tema_nombre || post.tema || '',
    tipo_post:       post.tipo_post  || '',
    tono:            post.tono       || '',
    fecha:           post.fecha_pub  || '',
    likes, comments, reposts, views,
    engagement_rate: Math.round(er_num * 10000) / 10000,
    er_percent:      (er_num * 100).toFixed(3) + '%',
    fuente_stats:    fuente
  };
});

if (!metricas.length) {
  return [{ json: { _sin_metricas: true, mensaje: 'No hay posts para procesar métricas' } }];
}

// Resumen por área
const erPorArea = {};
metricas.forEach(m => {
  const a = m.area || 'general';
  if (!erPorArea[a]) erPorArea[a] = { sum: 0, count: 0 };
  erPorArea[a].sum += m.engagement_rate;
  erPorArea[a].count++;
});

const resumen_areas = Object.entries(erPorArea)
  .map(([area, d]) => ({
    area,
    er_promedio:  (d.sum / d.count).toFixed(4),
    posts_count:  d.count
  }))
  .sort((a, b) => parseFloat(b.er_promedio) - parseFloat(a.er_promedio));

return [{ json: { metricas, resumen_areas, total_posts: metricas.length, li_posts_en_api: li_elements.length } }];
'''

CODE_DETECTAR_OUTLIERS = r'''
const data = $json;
if (data._sin_metricas) return [{ json: data }];

const metricas = data.metricas || [];
const ers = metricas.map(m => m.engagement_rate).filter(e => e > 0).sort((a, b) => a - b);

if (ers.length < 2) {
  return [{ json: { ...data, outliers_positivos: [], outliers_negativos: [], er_mediana: 0 } }];
}

const mediana = ers[Math.floor(ers.length / 2)];
const p75     = ers[Math.floor(ers.length * 0.75)] || mediana;

const outliers_positivos = metricas
  .filter(m => m.engagement_rate >= mediana * 2.0 && m.engagement_rate > 0)
  .map(m => ({ ...m, ratio_mediana: +(m.engagement_rate / mediana).toFixed(2) }));

const outliers_negativos = metricas
  .filter(m => m.engagement_rate > 0 && m.engagement_rate < mediana * 0.35)
  .map(m => ({ ...m, ratio_mediana: +(m.engagement_rate / mediana).toFixed(2) }));

return [{
  json: {
    ...data,
    er_mediana:         mediana,
    er_p75:             p75,
    outliers_positivos,
    outliers_negativos,
    tiene_outliers_pos: outliers_positivos.length > 0
  }
}];
'''

CODE_PREP_METRICAS_APPEND = r'''
const data = $json;
if (data._sin_metricas) return [];
// Solo guarda posts que tengan engagement_rate > 0 o datos reales de LinkedIn API
return (data.metricas || [])
  .filter(m => m.engagement_rate > 0 || m.fuente_stats === 'linkedin_api')
  .map(m => ({ json: m }));
'''

CODE_PREP_ANALYSIS = r'''
const data = $json;
if (data._sin_metricas) return [{ json: data }];

const metricas  = data.metricas || [];
const resumen   = data.resumen_areas || [];
const outliers_pos = data.outliers_positivos || [];
const er_mediana   = data.er_mediana || 0;

const ers = metricas.map(m => m.engagement_rate).filter(e => e > 0).sort((a, b) => a - b);
const er_p75 = ers.length ? ers[Math.floor(ers.length * 0.75)] : 0;

const top_posts = [...metricas]
  .sort((a, b) => b.engagement_rate - a.engagement_rate)
  .slice(0, 5)
  .map(p => `- ${p.tema || p.area}: ER=${(p.engagement_rate * 100).toFixed(2)}% (${p.likes}♥ ${p.comments}💬) [${p.fuente_stats}]`);

const out_txt = outliers_pos.slice(0, 3)
  .map(p => `  * ${p.tema || p.area}: ER=${(p.engagement_rate * 100).toFixed(2)}% = ${p.ratio_mediana}x mediana`);

const texto_analisis = [
  `MÉTRICAS DE ${metricas.length} POSTS:`,
  `ER mediana: ${(er_mediana * 100).toFixed(3)}% | ER top 25%: ${(er_p75 * 100).toFixed(3)}%`,
  `Posts con datos LinkedIn API: ${metricas.filter(m => m.fuente_stats === 'linkedin_api').length}`,
  `Posts con datos históricos: ${metricas.filter(m => m.fuente_stats === 'sheet_historico').length}`,
  ``,
  `RENDIMIENTO POR ÁREA:`,
  ...resumen.map(r => `- ${r.area}: ER promedio ${(parseFloat(r.er_promedio) * 100).toFixed(2)}% (${r.posts_count} posts)`),
  ``,
  ...(outliers_pos.length > 0 ? [`OUTLIERS POSITIVOS (ER > 2x mediana):`, ...out_txt, ``] : []),
  `TOP 5 POSTS POR ER:`,
  ...top_posts,
  ``,
  `DETALLE:`,
  ...metricas.slice(0, 20).map(m =>
    `${m.fecha || '?'} | ${m.area} | ${m.tono || '?'} | ER=${(m.engagement_rate * 100).toFixed(2)}% | ${m.likes}♥ ${m.comments}💬 ${m.views}👁 [${m.fuente_stats}]`
  )
].join('\n');

return [{ json: { ...data, texto_analisis: texto_analisis.substring(0, 9000) } }];
'''

CODE_PARSEAR_INSIGHTS = r'''
const raw = $json.message?.content || $json.choices?.[0]?.message?.content || '';
if (!raw) return [{ json: { insights: null, usar_basico: true } }];
let s = raw.trim().replace(/```json\s*/gi, '').replace(/```/g, '').trim();
const tm = s.match(/<\/think>\s*([\s\S]*)/); if (tm) s = tm[1].trim();
let ins;
try { ins = JSON.parse(s); }
catch(e) { const m = s.match(/\{[\s\S]*\}/); ins = m ? JSON.parse(m[0]) : null; }
const data_prev = $('Preparar Texto Análisis').first().json;
return [{ json: { ...data_prev, insights: ins } }];
'''

CODE_ACTUALIZAR_SCORES = r'''
const data = $json;
const insights   = data.insights || {};
const resumen    = data.resumen_areas || [];
const temas_sheet= $('Leer Temas para Scores').all().map(i => i.json);

const boostPorArea = {};
if (resumen.length > 0) {
  const er_max = Math.max(...resumen.map(r => parseFloat(r.er_promedio)));
  const er_min = Math.min(...resumen.map(r => parseFloat(r.er_promedio)));
  const rango  = er_max - er_min || 0.001;
  resumen.forEach(r => {
    const er = parseFloat(r.er_promedio);
    boostPorArea[r.area] = 0.8 + ((er - er_min) / rango) * 0.6;
  });
}

const areas_top = (insights?.areas_top || []).map(a => a.toLowerCase());

return temas_sheet
  .filter(t => t.id && t.estado !== 'publicado')
  .map(t => {
    const area  = (t.area || '').toLowerCase();
    const boost = boostPorArea[area] || 1.0;
    const score = parseFloat(t.score || '1.0');
    const score_nuevo = Math.round(score * (0.7 + boost * 0.3) * 100) / 100;
    const score_final = areas_top.includes(area)
      ? Math.min(score_nuevo * 1.2, 3.0)
      : Math.min(score_nuevo, 2.5);
    return { json: { id: t.id, score: score_final.toFixed(2) } };
  });
'''

CODE_PREP_INFORME = r'''
const data    = $('Parsear Insights Qwen').first().json || {};
const ins     = data.insights || {};
const res     = data.resumen_areas || [];
const total   = data.total_posts || 0;
const out_pos = (data.outliers_positivos || []).slice(0, 3);
const li_posts = data.li_posts_en_api || 0;

const areas_html = res.slice(0, 5).map(r =>
  `  • <b>${r.area}</b>: ER ${(parseFloat(r.er_promedio) * 100).toFixed(2)}% (${r.posts_count} posts)`
).join('\n');

const out_html = out_pos.length
  ? out_pos.map(p => `  🌟 ${p.tema || p.area}: ER ${(p.engagement_rate * 100).toFixed(2)}% (${p.ratio_mediana}x mediana)`).join('\n')
  : '  Ninguno detectado';

const rec = (ins?.recomendaciones_tono || []).slice(0, 3).join('\n  • ') || 'Sin recomendaciones';
const areas_top = (ins?.areas_top || []).join(', ') || 'datos insuficientes';
const patron = ins?.patron_detectado || '';

const msg = [
  `📊 <b>[ANALYST v2] Informe Engagement</b>`,
  ``,
  `Posts analizados: ${total} | LinkedIn API: ${li_posts} posts`,
  ``,
  `<b>ER por área:</b>`,
  areas_html || '  (sin datos)',
  ``,
  `<b>Outliers positivos:</b>`,
  out_html,
  ``,
  `<b>Áreas de mayor tracción:</b> ${areas_top}`,
  ``,
  ...(patron ? [`<b>Patrón detectado:</b> ${patron}`, ``] : []),
  `<b>Recomendaciones de tono:</b>`,
  `  • ${rec}`,
  ``,
  `Scores de temas actualizados ✅`
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
    '"patron_detectado":"el patrón más significativo encontrado (1-2 oraciones)",'
    '"recomendaciones_tono":["recomendación 1 para próximos posts","recomendación 2","recomendación 3"],'
    '"temas_a_reforzar":["tema o área a priorizar esta semana"],'
    '"alerta":"si hay algo preocupante en las métricas, sino vacío"}'
)

# ─── BUILD ────────────────────────────────────────────────────────────

def build():
    nodes = []
    conn  = {}
    def add(n): nodes.append(n); return n

    # Triggers
    sched = add(n_schedule("Trigger Analyst Diario", "0 23 * * 1,3,5", [0, -200]))
    wh    = add(n_webhook ("Webhook Analyst Manual", "ma-analyst-manual", [0, 200]))

    # Leer datos en paralelo
    leer_t = add(n_sheets_read("Leer Temas Sheet",   "Temas",    TEMAS_GID,    [260, 0]))
    leer_m = add(n_sheets_read("Leer Metricas Sheet","Metricas", METRICAS_GID, [260, 300]))

    # Filtrar posts publicados recientes
    filtrar = add(n_code("Filtrar Posts a Actualizar", CODE_FILTRAR_POSTS, [520, 0]))

    # ── Reemplaza Apify: LinkedIn API nativa (cero costo) ──
    li_get  = add(n_http_get(
        "Obtener Posts LinkedIn",
        LI_URL,
        [780, 0],
        headers_extra={
            "Authorization":               f"Bearer {LINKEDIN_TOKEN}",
            "X-Restli-Protocol-Version":   "2.0.0",
            "LinkedIn-Version":            "202301"
        }
    ))

    # Procesar métricas (LinkedIn API + histórico del Sheet)
    proc_m  = add(n_code("Procesar Métricas",    CODE_PROCESAR_METRICAS,  [1040, 0]))
    detectar= add(n_code("Detectar Outliers",    CODE_DETECTAR_OUTLIERS,  [1300, 0]))
    prep_ap = add(n_code("Preparar para Append", CODE_PREP_METRICAS_APPEND,[1560, 0]))

    # Guardar métricas frescas en Sheet
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

    # Análisis Qwen
    prep_txt = add(n_code("Preparar Texto Análisis", CODE_PREP_ANALYSIS,   [2080, 0]))
    qwen_ins = add(n_llm("🧠 Agente Analyst Qwen",
                          SYS_ANALYST, PROMPT_ANALYST, 0.3, 1400, [2340, 0]))
    pars_ins = add(n_code("Parsear Insights Qwen",  CODE_PARSEAR_INSIGHTS, [2600, 0]))

    # Actualizar scores (sequential: leer primero, luego calcular, luego guardar)
    leer_ts  = add(n_sheets_read("Leer Temas para Scores", "Temas", TEMAS_GID, [2600, 300]))
    act_sc   = add(n_code("Actualizar Scores Temas", CODE_ACTUALIZAR_SCORES, [2860, 0]))
    upd_sc   = add(n_sheets_update("Update Scores Sheet", TEMAS_GID, "Temas", {
        "id":    "={{ $json.id }}",
        "score": "={{ $json.score }}"
    }, "id", [3120, 0]))

    # Informe + FEEDBACK + Telegram
    prep_inf  = add(n_code("Preparar Informe", CODE_PREP_INFORME, [3380, 0]))
    call_fb   = add(n_http_post(
        "Llamar FEEDBACK Webhook",
        FEEDBACK_WH,
        [3640, 0],
        body_json=json.dumps({"trigger": "analyst", "timestamp": "={{ $now.toISO() }}"})
    ))
    tg_inf    = add(n_tg("Telegram Informe 📊", CHAT_ID, "={{ $json.mensaje }}", [3900, 0]))

    # ── CONEXIONES ─────────────────────────────────────────────────────
    for trigger in [sched["name"], wh["name"]]:
        connect(conn, trigger, leer_t["name"])
        connect(conn, trigger, leer_m["name"])

    connect(conn, leer_t["name"],   filtrar["name"])
    connect(conn, filtrar["name"],  li_get["name"])
    connect(conn, li_get["name"],   proc_m["name"])
    connect(conn, proc_m["name"],   detectar["name"])
    connect(conn, detectar["name"], prep_ap["name"])
    connect(conn, prep_ap["name"],  save_m["name"])
    connect(conn, save_m["name"],   prep_txt["name"])
    connect(conn, prep_txt["name"], qwen_ins["name"])
    connect(conn, qwen_ins["name"], pars_ins["name"])
    # Sequential: insights → leer temas → actualizar → guardar
    connect(conn, pars_ins["name"], leer_ts["name"])
    connect(conn, leer_ts["name"],  act_sc["name"])
    connect(conn, act_sc["name"],   upd_sc["name"])
    connect(conn, upd_sc["name"],   prep_inf["name"])
    connect(conn, prep_inf["name"], call_fb["name"])
    connect(conn, call_fb["name"],  tg_inf["name"])

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
    print("Actualizando [MA] ANALYST v2 — LinkedIn API (sin Apify)...")
    wf = build()
    print(f"  Nodos: {len(wf['nodes'])}")
    print(f"  Conexiones src: {len(wf['connections'])}")

    # PUT to replace existing workflow
    r = requests.put(
        f"{BASE_URL}/workflows/{ANALYST_ID}",
        headers=HEADERS,
        json=wf,
        timeout=30
    )
    if r.status_code in (200, 201):
        d = r.json()
        wid = d.get("id", ANALYST_ID)
        print(f"  ✅ ANALYST v2 actualizado — ID: {wid}")
        print(f"  Webhook manual: https://n8n.camiloayala.net/webhook/ma-analyst-manual")
        print(f"  UI: https://n8n.camiloayala.net/workflow/{wid}")
        # Re-activate
        ra = requests.post(f"{BASE_URL}/workflows/{wid}/activate", headers=HEADERS, timeout=10)
        print(f"  Activar: {ra.status_code}")
    else:
        print(f"  ❌ Error {r.status_code}: {r.text[:600]}")
