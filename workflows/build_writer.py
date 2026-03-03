#!/usr/bin/env python3
"""
[MA] WRITER — Motor Multi-Agente 3 Pasos
Arquitectura limpia con 2 caminos independientes:
  PATH A (Generación):  Trigger → LLM ×3 → Guardar → Telegram
  PATH B (Aprobación):  Telegram Webhook → Publicar LinkedIn
"""
import json, uuid, requests

API_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0YmY4ODRkNC1hMGUxLTRiNjgtOTVlZC1kMDc0ZWY5N2ExZDQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOWY0MWY5OWQtZDNkNy00NWNjLWFkZjAtZjc2ZmMwZDQxZjcyIiwiaWF0IjoxNzcxNzcyMzg4fQ.RmQl5yX4T9pAUn4swhvMcydMv-8VukNnlbPc7NgbK0U"
BASE_URL = "https://n8n.camiloayala.net/api/v1"
HEADERS  = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}

SHEETS_ID      = "1TmHXCe_68qA8GDZhZfzK-qvOh0H09tZqAF3UI5nWSrI"
TEMAS_GID      = 1090471100
METRICAS_GID   = 830260036
RECHAZOS_GID   = 148549058
CHAT_ID        = "1160149765"
BOT_TOKEN      = "BOT_TOKEN"
TELEGRAM_API   = f"https://api.telegram.org/bot{BOT_TOKEN}"
LINKEDIN_TOKEN = "LINKEDIN_BEARER_TOKEN_HERE  # set via N8N credential or env"
LINKEDIN_AUTHOR = "urn:li:person:jAuei1KlC1"
QWEN           = "qwen2.5:32b"
CRED_SHEETS    = {"id": "59A9Vs89LRQlZq9m", "name": "Google Sheets account"}
CRED_OLLAMA    = {"id": "S4LeOiFztrgDaMM9", "name": "Ollama"}
CRED_TELEGRAM  = {"id": "gR2WcHsnoq4oIAuT", "name": "Telegram account"}
UNSPLASH_KEY   = "UNSPLASH_ACCESS_KEY_HERE"

def nid(): return str(uuid.uuid4())

# ─── NODE BUILDERS ────────────────────────────────────────────────────

def n_schedule(name, cron, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.1, "position": pos,
            "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": cron}]}}}

def n_webhook(name, path, pos, response_mode="responseNode"):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.webhook",
            "typeVersion": 2, "position": pos,
            "parameters": {"httpMethod": "POST", "path": path,
                           "responseMode": response_mode, "options": {}}}

def n_code(name, js, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.code",
            "typeVersion": 2, "position": pos, "parameters": {"jsCode": js}}

def n_http(name, method, url, pos, body_json=None, headers_extra=None, form_params=None):
    p = {"method": method.upper(), "url": url,
         "options": {"response": {"response": {"neverError": True}}}}
    if headers_extra:
        p["sendHeaders"] = True
        p["headerParameters"] = {"parameters": [{"name": k, "value": v}
                                                  for k,v in headers_extra.items()]}
    if body_json is not None:
        p["sendBody"] = True
        p["specifyBody"] = "json"
        p["jsonBody"] = body_json if isinstance(body_json, str) else json.dumps(body_json)
    if form_params is not None:
        p["sendBody"] = True
        p["contentType"] = "form-urlencoded"
        p["bodyParameters"] = {"parameters": [{"name": k, "value": v}
                                                for k,v in form_params.items()]}
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

def n_merge(name, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.merge",
            "typeVersion": 3, "position": pos,
            "parameters": {"mode": "combine", "combineBy": "combineAll", "options": {}}}

def n_if(name, left, op, right, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.if",
            "typeVersion": 2.2, "position": pos,
            "parameters": {"conditions": {"options": {"caseSensitive": False},
                "conditions": [{"id": nid(), "leftValue": left,
                                "operator": {"type": "string", "operation": op},
                                "rightValue": right}]}}}

def n_switch(name, expr, cases, pos):
    rules = [{"conditions": {"options": {}, "conditions": [
        {"id": nid(), "leftValue": expr,
         "operator": {"type": "string", "operation": "equals"}, "rightValue": v}
    ]}} for v in cases]
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.switch",
            "typeVersion": 3.2, "position": pos,
            "parameters": {"mode": "rules", "rules": {"values": rules},
                           "options": {"fallbackOutput": "extra"}}}

def n_respond(name, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1, "position": pos,
            "parameters": {"respondWith": "text", "responseBody": "OK", "options": {}}}

def n_http_bin_download(name, url, pos):
    """HTTP GET node que descarga respuesta binaria (imagen)."""
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2, "position": pos,
            "parameters": {"method": "GET", "url": url,
                           "options": {"response": {"response": {"neverError": True}},
                                       "timeout": 30000}}}

def n_http_bin_upload(name, url, pos, auth_token):
    """HTTP PUT node que sube datos binarios (imagen) a LinkedIn."""
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2, "position": pos,
            "parameters": {
                "method": "PUT", "url": url,
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "Authorization",     "value": f"Bearer {auth_token}"},
                    {"name": "media-type-family", "value": "STILLIMAGE"},
                    {"name": "Content-Type",      "value": "image/jpeg"}
                ]},
                "sendBody": True,
                "contentType": "binaryData",
                "inputDataFieldName": "data",
                "options": {"response": {"response": {"neverError": True}},
                            "timeout": 30000}}}

def n_tg(name, chat_id, text, pos):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.telegram",
            "typeVersion": 1.2, "position": pos,
            "parameters": {"chatId": chat_id, "text": text,
                           "additionalFields": {"parse_mode": "HTML"}},
            "credentials": {"telegramApi": CRED_TELEGRAM}}

def connect(conn, src, dst, out=0, inp=0):
    if src not in conn: conn[src] = {"main": []}
    while len(conn[src]["main"]) <= out: conn[src]["main"].append([])
    conn[src]["main"][out].append({"node": dst, "type": "main", "index": inp})

# ─── PROMPTS ──────────────────────────────────────────────────────────

SYS_CAMILO = (
    "Actúas como estratega senior de contenido para LinkedIn especializado en "
    "posicionamiento de profesionales creativos latinoamericanos.\n\n"
    "Escribes en primera persona como Camilo Ayala Monje (@camiloayalam).\n\n"
    "PERFIL REAL DE CAMILO:\n"
    "- Comunicador y diseñador estratégico con 12+ años de experiencia\n"
    "- Profesor en Universidad El Bosque (Coordinador de Admisiones + Docente en Diseño de Comunicación)\n"
    "- Ex-profesor Universidad de Los Andes (7 años) y Universidad Sergio Arboleda\n"
    "- Especialidades: Diseño estratégico, comunicación digital, educación, marca personal para creativos\n"
    "- Bogotá, Colombia\n\n"
    "RED REAL (5,065 conexiones):\n"
    "- Top: Diseñador gráfico, Director creativo, CEO, Gerente general, Community Manager, Founder\n"
    "- Perfil dominante: líderes creativos, directores, fundadores en Colombia y Latam\n"
    "- Industrias: Diseño, Educación, Publicidad, Marketing digital\n\n"
    "ÁREAS DE AUTORIDAD:\n"
    "1. Innovación en educación y comunicación digital\n"
    "2. Diseño estratégico y creatividad aplicada\n"
    "3. Marketing digital y automatización\n"
    "4. Marca personal para creativos latinoamericanos\n\n"
    "REGLAS DE ESCRITURA — CRÍTICAS:\n"
    "- Escribe como un humano culto que piensa en voz alta, NO como una IA generando contenido\n"
    "- Oraciones cortas cuando hay tensión. Párrafos cortos. Nunca más de 3 líneas seguidas\n"
    "- PROHIBIDO inventar estadísticas, porcentajes, encuestas o datos que no existan\n"
    "- PROHIBIDO inventar nombres de personas reales (Juan Pablo, María, etc.)\n"
    "- PROHIBIDO repetir la misma idea dos veces en el mismo post\n"
    "- PROHIBIDO frases de IA: En el mundo actual, Es fundamental, La clave está en, Es importante, "
    "cada vez más, Sin lugar a dudas, No es casualidad que, Más allá de, En definitiva, "
    "Lo que muchos no saben, Esto nos lleva a, Cabe mencionar, Vale la pena destacar\n"
    "- Sin emojis. Sin signos de exclamación. Entre 1800 y 2500 caracteres\n"
    "- Párrafos separados por línea en blanco. Nunca bloques de texto corrido\n"
    "- Postura clara y propia — nunca neutral, nunca motivacional genérico\n"
    "- Si usas un dato, que sea verificable o presentado como experiencia personal\n"
    "- La voz es directa, con criterio, sin grandilocuencia\n\n"
    "LENGUAJE: español bogotano culto — neutro, directo, sin afectación regional\n"
    "VOCABULARIO PROHIBIDO: sinergia, disruptivo, innovador, transformacional, paradigma, "
    "ecosistema, impacto positivo, empoderamiento\n\n"
    "Responde ÚNICAMENTE con JSON válido. Sin backticks, sin markdown, sin texto adicional."
)

PROMPT_ANALISTA = (
    "Analiza este tema y construye el plan estratégico para el post de LinkedIn de Camilo. "
    "NO escribes el post. Solo planeas. Sé ultra-específico.\n\n"
    "TEMA: {{ $json.tema }}\n"
    "TIPO: {{ $json.tipo_post || 'reflexión' }}\n"
    "PROFUNDIDAD: {{ $json.nivel_profundidad || 'avanzado' }}\n"
    "OBJETIVO: {{ $json.objetivo || 'posicionamiento' }}\n"
    "DÍA: {{ $json.contexto_dia }}\n\n"
    "Devuelve EXACTAMENTE este JSON (sin backticks):\n"
    '{"tension":"paradoja o contradicción real en este tema — lo no obvio (2-3 oraciones concretas)",'
    '"ejemplo_concreto":"ejemplo verificable de la experiencia docente o profesional de Camilo, sin inventar personas",'
    '"creencia_a_contradecir":"creencia común del sector que el post va a refutar",'
    '"postura_central":"posición directa y no obvia de Camilo — lo que alguien con criterio propio diría",'
    '"gancho":"primera oración del post: máximo 15 palabras, tensión inmediata, sin exclamaciones ni preguntas retóricas vacías",'
    '"puntos_desarrollo":["punto 1: tensión concreta","punto 2: argumento con ejemplo","punto 3: implicación no obvia","punto 4: postura final"],'
    '"palabras_prohibidas_contexto":["3-5 palabras específicas a este tema que suenan genéricas"]}'
)

PROMPT_ESCRITOR = (
    "{{ $json.system_prompt }}\n\n"
    "Escribe el post completo de LinkedIn. SIGUE OBLIGATORIAMENTE EL PLAN.\n\n"
    "TEMA: {{ $json.tema }}\n"
    "TIPO: {{ $json.tipo_post }}\n"
    "TONO: {{ $json.tono }}\n"
    "AJUSTE HISTÓRICO: {{ $json.tone_hint }}\n\n"
    "PLAN ESTRATÉGICO A SEGUIR:\n{{ $json.outline_injection }}\n\n"
    "REGLAS OBLIGATORIAS:\n"
    "- Entre 1800 y 2500 caracteres. Cuenta antes de responder. Si tienes menos de 1800, expande el argumento central\n"
    "- Párrafos separados por línea en blanco. Máximo 3 líneas por párrafo\n"
    "- Sin emojis, sin signos de exclamación, sin bullets\n"
    "- Empieza con el GANCHO del plan\n"
    "- Al final: exactamente 4 hashtags separados por espacio\n\n"
    "Responde ÚNICAMENTE con JSON válido (sin backticks):\n"
    '{"post_text":"texto completo del post con los 4 hashtags al final",'
    '"hook_type":"tension|dato|pregunta|postura",'
    '"imagen_descripcion":"2-4 palabras en inglés para Unsplash, concretas y visuales",'
    '"hashtags":["#hashtag1","#hashtag2","#hashtag3","#hashtag4"]}'
)

PROMPT_HUMANIZADOR_SYS = (
    "Eres un editor experto que detecta y elimina el lenguaje artificial de posts de LinkedIn.\n"
    "Conoces exactamente los patrones de escritura de Camilo Ayala Monje: directo, culto, "
    "sin grandilocuencia, español bogotano formal.\n"
    "Responde ÚNICAMENTE con JSON válido. Sin backticks, sin markdown."
)

PROMPT_HUMANIZADOR = (
    "Humaniza el campo post_text. Mantén hook_type, imagen_descripcion y hashtags exactamente igual.\n\n"
    "SEÑALES DE IA A ELIMINAR:\n"
    "- Aperturas: En el mundo actual, Vivimos en una era, En los últimos años, Cada vez más\n"
    "- Conectores: Es importante destacar, Cabe mencionar, Vale la pena señalar, Es fundamental\n"
    "- Certezas: Sin lugar a dudas, No es casualidad que, Definitivamente, Por supuesto\n"
    "- Transiciones: Y es que, Por ello, En definitiva, Esto nos lleva a, De esta manera\n"
    "- Vocabulario: sinergia, disruptivo, innovador, transformacional, paradigma, ecosistema, impacto, empoderamiento\n"
    "- Coach LinkedIn: El éxito llega cuando, Si quieres crecer debes, La clave del éxito es, Recuerda que\n"
    "- Moraleja final genérica al final del post\n"
    "- Repetición de ideas con distintas palabras\n\n"
    "REGLAS: mismo largo y estructura. NO agregues ideas nuevas. Correcciones quirúrgicas.\n\n"
    "DRAFT JSON:\n{{ $json.draft_json_str }}\n\n"
    "Devuelve el mismo JSON con post_text humanizado (sin backticks):\n"
    '{"post_text":"texto humanizado","hook_type":"mismo valor","imagen_descripcion":"mismo valor","hashtags":["mismos","hashtags"]}'
)

# ─── CÓDIGO NODES ─────────────────────────────────────────────────────

CODE_PARSEAR_SHEETS = '''
const all = $input.all().map(i => i.json);
const temas_raw    = all.filter(i => 'id' in i && 'tema' in i && 'score' in i);
const metricas_raw = all.filter(i => 'post_id' in i && 'likes' in i);
const rechazos_raw = all.filter(i => 'motivo' in i && !('score' in i));
const temasMap = {};
for (const t of temas_raw) {
  const id = (t.id || '').trim();
  if (!id) continue;
  if (!temasMap[id] || (t.row_number || 999) < (temasMap[id].row_number || 999)) temasMap[id] = t;
}
return [{ json: { temas: Object.values(temasMap), metricas: metricas_raw, rechazos: rechazos_raw } }];
'''

CODE_PRIORIDAD = '''
const { temas, metricas, rechazos } = $('Parsear Sheets').first().json;
const ahora = Date.now();
const candidatos = temas.filter(t => {
  const e = (t.estado || '').toLowerCase().trim();
  if (!e || e === 'pendiente' || e === 'disponible') return true;
  if (e === 'publicado' && t.fecha_pub) return (ahora - new Date(t.fecha_pub).getTime()) > 21*86400000;
  return false;
});
if (!candidatos.length) throw new Error('Sin temas disponibles en el Sheet Temas.');

const erPorArea = {};
metricas.forEach(m => { const a = m.area||m.tema||''; const er = parseFloat(m.engagement_rate)||0; if (!erPorArea[a]) erPorArea[a]=[]; erPorArea[a].push(er); });
const todosER = metricas.map(m => parseFloat(m.engagement_rate)||0).filter(e=>e>0).sort((a,b)=>a-b);
const p25 = todosER[Math.floor(todosER.length*.25)]||0.0097;
const p75 = todosER[Math.floor(todosER.length*.75)]||0.0181;
const hace14 = ahora - 14*86400000;
const rechRec = {};
rechazos.forEach(r => { const f = new Date(r.fecha||0).getTime(); if(f>hace14) rechRec[r.tema_id]=(rechRec[r.tema_id]||0)+1; });

const dw = new Date().getDay();
const tonosDia = {1:'reflexivo',3:'herramienta',5:'provocador'};
const tonoCtx = tonosDia[dw]||'directo';
const dias = ['domingo','lunes','martes','miércoles','jueves','viernes','sábado'];

candidatos.forEach(t => {
  let s = parseFloat(t.score||1);
  s *= (1 - Math.min(parseInt(t.veces_publicado||0)*.20, .60));
  if (t.fecha_pub) { const d=(ahora-new Date(t.fecha_pub).getTime())/86400000; s*=(1+Math.min((d/7)*.05,.40)); } else s*=1.5;
  const erA = erPorArea[t.area||'']||[];
  if (erA.length) { const avg=erA.reduce((a,b)=>a+b,0)/erA.length; if(avg>p75)s*=1.3; else if(avg<p25)s*=0.8; }
  s *= Math.pow(.75, rechRec[t.id]||0);
  if ((t.tono||'').toLowerCase()===tonoCtx) s*=1.05;
  s *= (.85+Math.random()*.45);
  if (t.fecha_propuesto) { const dp=(ahora-new Date(t.fecha_propuesto).getTime())/86400000; if(dp<7)s*=.4; }
  t.score_final = Math.round(s*100)/100;
});

const top3 = candidatos.sort((a,b)=>b.score_final-a.score_final).slice(0,3);
const total = top3.reduce((a,t)=>a+t.score_final,0);
let r = Math.random()*total, ganador = top3[0];
for (const t of top3) { r -= t.score_final; if (r<=0) { ganador=t; break; } }
const erProm = todosER.length ? todosER.reduce((a,b)=>a+b,0)/todosER.length : 0.0139;

return [{ json: {
  ...ganador,
  tema: ganador.tema_nombre || ganador.tema,
  tipo_post: ganador.tipo_post||'reflexión',
  nivel_profundidad: ganador.nivel_profundidad||'avanzado',
  tono: ganador.tono||tonoCtx,
  objetivo: ganador.objetivo||'posicionamiento',
  contexto_dia: `${dias[dw]} — tono recomendado: ${tonoCtx}`,
  tone_hint: `ER promedio histórico: ${(erProm*100).toFixed(2)}%`,
  er_promedio: erProm
}}];
'''

_sys_js = SYS_CAMILO  # No backticks or ${} — safe for JS template literal
CODE_SYS_PROMPT = "const sp = `" + _sys_js + "`;\nreturn [{ json: { system_prompt: sp } }];"

CODE_CTX = '''
const tema = $('Calcular Prioridad').first().json;
const sp   = $('System Prompt').first().json.system_prompt;
return [{ json: { ...tema, system_prompt: sp } }];
'''

CODE_PARSEAR_OUTLINE = r'''
const raw = $json.message?.content || $json.choices?.[0]?.message?.content || '';
if (!raw) throw new Error('Agente Analista vacío');
let s = raw.trim().replace(/```json\s*/gi,'').replace(/```/g,'').trim();
const tm = s.match(/<\/think>\s*([\s\S]*)/); if (tm) s = tm[1].trim();
let o;
try { o = JSON.parse(s); } catch(e) { const m=s.match(/\{[\s\S]*\}/); if(!m) throw new Error('Sin JSON en Analista: '+s.substring(0,200)); o=JSON.parse(m[0]); }
const pts = (o.puntos_desarrollo||[]).join('\n→ ');
const proh = (o.palabras_prohibidas_contexto||[]).join(', ');
const inj = `TENSIÓN: ${o.tension||''}\nEJEMPLO CONCRETO: ${o.ejemplo_concreto||''}\nCREENCIA A CONTRADECIR: ${o.creencia_a_contradecir||''}\nPOSTURA FINAL: ${o.postura_central||''}\nGANCHO (usa este inicio exacto): "${o.gancho||''}"\nPUNTOS A DESARROLLAR:\n→ ${pts}\nPALABRAS PROHIBIDAS EN ESTE POST: ${proh}`;
return [{ json: { ...$('Combinar Contexto').first().json, outline: o, outline_injection: inj } }];
'''

CODE_PARSEAR_DRAFT = r'''
const raw = $json.message?.content || $json.choices?.[0]?.message?.content || '';
if (!raw) throw new Error('Agente Escritor vacío');
let s = raw.trim().replace(/```json\s*/gi,'').replace(/```/g,'').trim();
const tm = s.match(/<\/think>\s*([\s\S]*)/); if (tm) s = tm[1].trim();
let d;
try { d = JSON.parse(s); } catch(e) {
  const m = s.match(/\{[\s\S]*\}/);
  if (!m) throw new Error('Sin JSON en Escritor: '+s.substring(0,200));
  let t = m[0];
  const op=(t.match(/\{/g)||[]).length, cl=(t.match(/\}/g)||[]).length;
  for(let i=0;i<op-cl;i++) t+='}';
  d = JSON.parse(t);
}
if (!d.post_text || d.post_text.length < 200) throw new Error('post_text muy corto: '+(d.post_text||'').length);
const prev = $('Parsear Outline').first().json;
return [{ json: { ...prev, draft: d, draft_json_str: JSON.stringify(d) } }];
'''

CODE_PARSEAR_FINAL = r'''
const raw = $json.message?.content || $json.choices?.[0]?.message?.content || '';
let s = (raw||'').trim().replace(/```json\s*/gi,'').replace(/```/g,'').trim();
const tm = s.match(/<\/think>\s*([\s\S]*)/); if (tm) s = tm[1].trim();
let fp;
try { fp = JSON.parse(s); } catch(e) { fp = $('Parsear Draft').first().json.draft || {}; }
let pt = (fp.post_text||'').trim().replace(/\r\n/g,'\n').replace(/\n{3,}/g,'\n\n').trim();
if (!pt || pt.length < 200) pt = $('Parsear Draft').first().json.draft?.post_text || '';
const base = $('Parsear Outline').first().json;
return [{ json: {
  ...base,
  post_text: pt,
  hook_type: fp.hook_type || 'directo',
  imagen_descripcion: fp.imagen_descripcion || base.imagen_descripcion || 'creative professional workspace',
  hashtags: fp.hashtags || base.hashtags || ['#diseño','#comunicación','#educación','#Colombia'],
  caracteres: pt.length,
  parrafos: pt.split('\n\n').filter(p=>p.trim()).length
}}];
'''

CODE_VALIDAR = r'''
const data = $json;
const texto = data.post_text || '';
let score = 100;
const problemas = [];
if (texto.length > 2700) { score -= 20; problemas.push('Largo: '+texto.length); }
else if (texto.length < 500) { score -= 35; problemas.push('Corto: '+texto.length); }
['en el mundo actual','es fundamental','la clave está en','es importante','cada vez más',
 'sin lugar a dudas','definitivamente','en definitiva','no es casualidad','más allá de',
 'lo que muchos no saben','esto nos lleva','cabe mencionar','vale la pena destacar',
 'sinergia','disruptivo','transformacional','paradigma','ecosistema','empoderamiento'
].forEach(f => { if (texto.toLowerCase().includes(f)) { score-=8; problemas.push(`IA:"${f}"`); } });
if (/\p{Emoji_Presentation}/u.test(texto)) { score-=25; problemas.push('Emojis'); }
const excl = (texto.match(/!/g)||[]).length;
if (excl>0) { score-=excl*15; problemas.push(`${excl} exclamaciones`); }
if (texto.split('\n\n').filter(p=>p.trim()).length < 3) { score-=15; problemas.push('Pocos párrafos'); }
if (/^(tema|tono|tipo|área|profundidad):/im.test(texto)) { score-=30; problemas.push('Metadata en texto'); }
if (texto.trim().startsWith('#')) { score-=20; problemas.push('Empieza con #'); }
score = Math.max(0, score);
return [{ json: { ...data, calidad_score: score, calidad_pasa: score >= 55, calidad_problemas: problemas,
  calidad_label: score>=80?'🟢 Bueno':score>=55?'🟡 Aceptable':'🔴 Bajo' } }];
'''

CODE_IMG_STRAT = f'''
const d = $json;
const desc = (d.imagen_descripcion||'creative workspace design').toLowerCase();
const temas_abstractos = ['marca personal','liderazgo','creatividad','identidad','educación',
  'aprendizaje','pensamiento','estrategia','comunicación','futuro','proceso','metodología'];
const es_abstracto = temas_abstractos.some(t => (d.tema||'').toLowerCase().includes(t) || (d.area||'').toLowerCase().includes(t));
const uq = encodeURIComponent(desc + ' professional editorial Colombia');
const pq = encodeURIComponent(desc + ', professional photography, editorial style, minimal, Colombia, creative');
return [{{ json: {{
  ...d,
  img_strat: es_abstracto ? 'pollinations' : 'unsplash',
  unsplash_url: 'https://api.unsplash.com/photos/random?query='+uq+'&orientation=landscape&client_id={UNSPLASH_KEY}',
  pollinations_url: 'https://image.pollinations.ai/prompt/'+pq+'?width=1200&height=628&nologo=true&model=flux'
}} }}];
'''

CODE_PREP_IMG = r'''
const d = $json;
const strat = d.img_strat || 'unsplash';
let img_url = '', img_credit = '';
try {
  const resp = $input.first().json;
  if (strat === 'unsplash') {
    img_url = resp.urls?.regular || resp.urls?.small || '';
    img_credit = 'Foto: ' + (resp.user?.name||'Unsplash') + ' en Unsplash';
  } else {
    img_url = d.pollinations_url || '';
    img_credit = 'Imagen: Pollinations AI';
  }
} catch(e) { img_url = ''; img_credit = ''; }
return [{ json: { ...d, imagen_url: img_url, imagen_credit: img_credit } }];
'''

CODE_PREP_TG = f'''
const d = $json;
const txt = (d.post_text||'');
const preview_text = txt.length > 600 ? txt.substring(0,597)+'...' : txt;
const hashtags = (d.hashtags||[]).join(' ');
const score = d.calidad_score||0;
const label = d.calidad_label||'';
const chars = d.caracteres || txt.length;
const outline = d.outline||{{}};

function esc(s){{ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}

const caption = [
  `📝 <b>${{esc(d.tema||'').substring(0,60)}}</b>`,
  `Calidad: ${{score}}/100 ${{label}} · ${{chars}} chars`,
  ``,
  `─── TENSIÓN (Analista) ───`,
  esc((outline.tension||'').substring(0,120)),
  ``,
  `─── INICIO DEL POST ───`,
  esc(preview_text.split('\\n\\n')[0]||''),
  ``,
  `─── PREVIEW ───`,
  esc(preview_text.substring(0,400)),
  ``,
  hashtags
].join('\\n');

const keyboard = JSON.stringify({{
  inline_keyboard: [[
    {{ text: '✅ Publicar', callback_data: `v2|aprobar|${{d.id}}` }},
    {{ text: '🔄 Regenerar', callback_data: `v2|regenerar|${{d.id}}` }},
    {{ text: '❌ Rechazar', callback_data: `v2|rechazar|${{d.id}}` }}
  ]]
}});

return [{{ json: {{ ...d, tg_caption: caption, tg_keyboard: keyboard }} }}];
'''

CODE_CB_PARSE = f'''
const body = $json.body || $json;
const cb = body.callback_query;
if (!cb) {{
  return [{{ json: {{ tipo: 'otro', accion: 'ignorar' }} }}];
}}
const data = cb.data || '';
const parts = data.split('|');
const es_v2 = parts[0] === 'v2';
const accion = es_v2 ? (parts[1]||'') : (parts[0]||'');
const tema_id = es_v2 ? (parts.slice(2).join('|')||'') : (parts.slice(1).join('|')||'');
return [{{ json: {{
  tipo: 'callback',
  accion,
  tema_id,
  callback_id: cb.id,
  message_id: cb.message?.message_id,
  chat_id: cb.message?.chat?.id || {CHAT_ID}
}} }}];
'''

CODE_LEER_POST_WS = '''
// Encuentra la fila del Sheet correspondiente al tema_id del callback
const cb = $('Parsear Callback').first().json;
const tema_id = cb.tema_id || '';
const todas = $input.all().map(i => i.json);
const fila = todas.find(r => String(r.id||'').trim() === String(tema_id).trim());
if (!fila) throw new Error('No se encontró tema_id="'+tema_id+'" en Temas Sheet');
if (!fila.post_text) throw new Error('tema_id="'+tema_id+'" no tiene post_text guardado. ¿El Writer guardó el post?');
return [{ json: { ...cb, ...fila } }];
'''

CODE_PREP_LI = f'''
const d = $json;
const body = {{
  author: '{LINKEDIN_AUTHOR}',
  lifecycleState: 'PUBLISHED',
  specificContent: {{
    'com.linkedin.ugc.ShareContent': {{
      shareCommentary: {{ text: d.post_text || '' }},
      shareMediaCategory: 'NONE'
    }}
  }},
  visibility: {{ 'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC' }}
}};
return [{{ json: {{ ...d, linkedin_body: JSON.stringify(body) }} }}];
'''

CODE_VAL_LI = '''
const resp = $json;
const status = resp.statusCode || resp.status || 200;
const post_id = resp.id || resp.headers?.['x-restli-id'] || 'unknown';
if (status >= 400) throw new Error('LinkedIn error '+status+': '+JSON.stringify(resp).substring(0,300));
// Funciona para ambas rutas: con imagen (Preparar Body Imagen) o sin imagen (Preparar LinkedIn Body)
let prev = {};
try { prev = $('Preparar Body Imagen').first().json; } catch(e) {}
if (!prev.post_text) { try { prev = $('Preparar LinkedIn Body').first().json; } catch(e) {} }
return [{ json: { ...prev, post_id, linkedin_status: status, publicado_en: new Date().toISOString() } }];
'''

CODE_SAVE_RECH = '''
const cb = $('Parsear Callback').first().json;
return [{ json: {
  tema_id: cb.tema_id,
  motivo:  'rechazado_telegram_v2',
  fecha:   new Date().toISOString().substring(0,16).replace('T',' ')
} }];
'''

REGISTER_UPLOAD_BODY = json.dumps({
    "registerUploadRequest": {
        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
        "owner": LINKEDIN_AUTHOR,
        "serviceRelationships": [{"relationshipType": "OWNER",
                                   "identifier": "urn:li:userGeneratedContent"}]
    }
})

CODE_EXTR_UP_AP = r'''
const reg = $json;
const mech = reg.value?.uploadMechanism;
const upload_url = mech?.['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']?.uploadUrl || '';
const asset_id = reg.value?.asset || '';
const fila = $('Encontrar Post Guardado').first().json;
return [{ json: { ...fila, upload_url, asset_id } }];
'''

CODE_PREP_BIN_AP = r'''
const asset = $('Extraer URL Upload').first().json;
const dlBinary = $('Descargar Imagen').first().binary;
const binaryData = (dlBinary && dlBinary.data) ? dlBinary : null;
if (!binaryData) throw new Error('No se pudo descargar la imagen para subir a LinkedIn');
return [{ json: asset, binary: binaryData }];
'''

CODE_PREP_LI_IMG = f'''
const d = $('Encontrar Post Guardado').first().json;
const asset_id = $('Extraer URL Upload').first().json.asset_id || '';
const imagen_credit = d.imagen_credit || '';
const credit_line = imagen_credit ? '\\n\\n📷 ' + imagen_credit : '';
const full_text = (d.post_text || '') + credit_line;
const body = {{
  author: '{LINKEDIN_AUTHOR}',
  lifecycleState: 'PUBLISHED',
  specificContent: {{
    'com.linkedin.ugc.ShareContent': {{
      shareCommentary: {{ text: full_text }},
      shareMediaCategory: 'IMAGE',
      media: [{{ status: 'READY', media: asset_id,
                description: {{ text: '' }}, title: {{ text: '' }} }}]
    }}
  }},
  visibility: {{ 'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC' }}
}};
return [{{ json: {{ ...d, linkedin_body: JSON.stringify(body), asset_id }} }}];
'''

# ─── BUILD WORKFLOW ───────────────────────────────────────────────────

def build():
    nodes = []
    conn  = {}
    def add(n): nodes.append(n); return n

    # ── PATH A: GENERACIÓN ────────────────────────────────────────────

    # Triggers
    sched  = add(n_schedule("Trigger Diario",   "0 14 * * 1,3,5", [0, -300]))
    wh_man = add(n_webhook ("Webhook Manual",   "ma-writer-manual", [0, 300]))

    # Leer sheets (3 en paralelo desde trigger)
    temas  = add(n_sheets_read("Leer Temas",    "Temas",    TEMAS_GID,    [260, 0]))
    metr   = add(n_sheets_read("Leer Metricas", "Metricas", METRICAS_GID, [260, -260]))
    rech   = add(n_sheets_read("Leer Rechazos", "Rechazos", RECHAZOS_GID, [260, 260]))
    merge  = add(n_merge      ("Merge Sheets",              [520, 0]))
    parse  = add(n_code       ("Parsear Sheets",    CODE_PARSEAR_SHEETS,  [780, 0]))
    prio   = add(n_code       ("Calcular Prioridad",CODE_PRIORIDAD,       [1040, 0]))
    sp     = add(n_code       ("System Prompt",     CODE_SYS_PROMPT,      [1300, 0]))
    ctx    = add(n_code       ("Combinar Contexto", CODE_CTX,             [1560, 0]))

    # 3-pass LLM
    an1    = add(n_llm("🔍 Agente Analista",
                       "Eres el estratega de contenido de Camilo Ayala. Analizas temas y "
                       "construyes planes estratégicos de posts para LinkedIn. NO escribes el post. "
                       "Solo planeas. Responde ÚNICAMENTE con JSON válido, sin backticks ni markdown.",
                       PROMPT_ANALISTA, 0.30, 1000, [1820, 0]))
    outline= add(n_code("Parsear Outline",    CODE_PARSEAR_OUTLINE,  [2080, 0]))

    an2    = add(n_llm("✍️ Agente Escritor",
                       "Eres Camilo Ayala Monje escribiendo un post de LinkedIn. Sigues el plan "
                       "del Agente Analista AL PIE DE LA LETRA. Responde ÚNICAMENTE con JSON válido, "
                       "sin backticks ni markdown.",
                       PROMPT_ESCRITOR, 0.75, 3800, [2340, 0]))
    draft  = add(n_code("Parsear Draft",      CODE_PARSEAR_DRAFT,    [2600, 0]))

    an3    = add(n_llm("🧹 Agente Humanizador",
                       PROMPT_HUMANIZADOR_SYS, PROMPT_HUMANIZADOR,
                       0.40, 3800, [2860, 0]))
    final  = add(n_code("Parsear Post Final", CODE_PARSEAR_FINAL,    [3120, 0]))
    valid  = add(n_code("Validar Calidad",    CODE_VALIDAR,          [3380, 0]))
    ifq    = add(n_if  ("¿Pasa Calidad?", "={{ $json.calidad_pasa }}", "equals", "true", [3640, 0]))

    # Imagen
    img_s  = add(n_code("Seleccionar Imagen",  CODE_IMG_STRAT,   [3900, 0]))
    uns    = add(n_http("Obtener Unsplash",    "GET", "={{ $json.unsplash_url }}",    [4160, -200]))
    pol    = add(n_http("Preparar Pollinations","GET","={{ $json.pollinations_url }}", [4160,  200]))
    img_f  = add(n_code("Preparar Imagen Final", CODE_PREP_IMG, [4420, 0]))

    # Preview Telegram
    tg_pre = add(n_code("Preparar Preview TG",  CODE_PREP_TG,  [4680, 0]))

    # Guardar post en Sheet con estado esperando (UPDATE por id)
    save_w = add(n_sheets_update("Guardar Post Pendiente", TEMAS_GID, "Temas", {
        "id":           "={{ $json.id }}",
        "post_text":    "={{ $json.post_text }}",
        "imagen_url":   "={{ $json.imagen_url }}",
        "imagen_credit":"={{ $json.imagen_credit }}",
        "estado":       "esperando_v2",
        "fecha_propuesto": "={{ $now.format('yyyy-MM-dd HH:mm') }}"
    }, "id", [4940, 0]))

    # Enviar foto + botones a Telegram
    tg_send = add(n_http("Enviar Aprobacion TG", "POST",
        f"{TELEGRAM_API}/sendPhoto", [5200, 0],
        body_json=json.dumps({
            "chat_id": int(CHAT_ID),
            "photo": "={{ $json.imagen_url || 'https://picsum.photos/1200/628' }}",
            "caption": "={{ $json.tg_caption }}",
            "parse_mode": "HTML",
            "reply_markup": "={{ $json.tg_keyboard }}"
        })
    ))

    # Notif baja calidad
    tg_low = add(n_tg("Notificar Baja Calidad", CHAT_ID,
        "⚠️ Post generado con calidad baja ({{ $json.calidad_score }}/100).\nProblemas: {{ $json.calidad_problemas.join(', ') }}\nSe descartó. Próximo ciclo intentará de nuevo.",
        [3900, 300]))

    # ── PATH B: APROBACIÓN ────────────────────────────────────────────

    tg_wh   = add(n_webhook("Telegram Entry MA",  "ma-telegram-v2", [0, 700]))
    ack_tg  = add(n_respond("ACK Telegram",                         [260, 700]))
    cb_par  = add(n_code   ("Parsear Callback",   CODE_CB_PARSE,    [520, 700]))

    # Answer callback (quitar loading en botón) — usa datos de cb_par directo
    ans_cb  = add(n_http("Answer Callback", "POST",
        f"{TELEGRAM_API}/answerCallbackQuery", [780, 700],
        form_params={"callback_query_id": "={{ $json.callback_id }}", "text": "✅"}
    ))

    # Actualizar markup (quitar botones del mensaje)
    # BUG FIX: referenciar Parsear Callback porque $json aquí es la respuesta HTTP de ans_cb
    upd_mkup = add(n_http("Limpiar Botones TG", "POST",
        f"{TELEGRAM_API}/editMessageReplyMarkup", [1040, 700],
        form_params={
            "chat_id":    "={{ $('Parsear Callback').first().json.chat_id }}",
            "message_id": "={{ $('Parsear Callback').first().json.message_id }}",
            "reply_markup": '{"inline_keyboard":[]}'
        }
    ))

    # BUG FIX: expresión correcta — $json.accion se pierde tras los nodos HTTP anteriores
    router  = add(n_switch("Router Decisión",
                            "={{ $('Parsear Callback').first().json.accion }}",
                            ["aprobar", "rechazar", "regenerar"], [1300, 700]))

    # -- APROBAR --
    lr_temas = add(n_sheets_read("Leer Temas Aprobacion", "Temas", TEMAS_GID, [1560, 560]))
    lr_fila  = add(n_code("Encontrar Post Guardado", CODE_LEER_POST_WS, [1820, 560]))

    # Verificar si hay imagen guardada en el Sheet
    if_img   = add(n_if("¿Tiene Imagen?",
                        "={{ $json.imagen_url }}", "notEquals", "", [2080, 560]))

    # -- APROBAR con imagen (TRUE): registrar asset → descargar → subir → publicar
    reg_ast  = add(n_http("Registrar Asset", "POST",
        "https://api.linkedin.com/v2/assets?action=registerUpload", [2340, 420],
        body_json=REGISTER_UPLOAD_BODY,
        headers_extra={
            "Authorization": f"Bearer {LINKEDIN_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
    ))
    extr_up  = add(n_code("Extraer URL Upload",   CODE_EXTR_UP_AP,   [2600, 420]))
    dl_img   = add(n_http_bin_download("Descargar Imagen",
        "={{ $('Encontrar Post Guardado').first().json.imagen_url }}", [2860, 420]))
    prp_bin  = add(n_code("Preparar Binario",      CODE_PREP_BIN_AP,  [3120, 420]))
    up_img   = add(n_http_bin_upload("Subir Imagen LinkedIn",
        "={{ $('Extraer URL Upload').first().json.upload_url }}", [3380, 420],
        LINKEDIN_TOKEN))
    prep_li_img = add(n_code("Preparar Body Imagen", CODE_PREP_LI_IMG, [3640, 420]))

    # -- APROBAR sin imagen (FALSE): publicar solo texto
    prep_li  = add(n_code("Preparar LinkedIn Body",  CODE_PREP_LI,      [2340, 700]))

    # Publicar (compartido por ambas rutas — solo una corre por ejecución)
    pub_li   = add(n_http("Publicar LinkedIn", "POST",
        "https://api.linkedin.com/v2/ugcPosts", [3900, 560],
        body_json="={{ $json.linkedin_body }}",
        headers_extra={
            "Authorization": f"Bearer {LINKEDIN_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
    ))
    val_li   = add(n_code("Validar LinkedIn",  CODE_VAL_LI, [4160, 560]))
    reg_pub  = add(n_sheets_update("Registrar Publicación", TEMAS_GID, "Temas", {
        "id":              "={{ $json.id }}",
        "estado":          "publicado",
        "fecha_pub":       "={{ $now.format('yyyy-MM-dd HH:mm') }}",
        "post_id":         "={{ $json.post_id }}",
        "veces_publicado": "={{ (parseInt($json.veces_publicado||0)) + 1 }}",
        "imagen_url":      "={{ $json.imagen_url || '' }}",
        "post_text":       "={{ $json.post_text || '' }}"
    }, "id", [4420, 560]))
    tg_ok    = add(n_tg("Telegram Publicado ✅", CHAT_ID,
        "✅ <b>Post publicado en LinkedIn</b>\n\nTema: {{ $json.tema_nombre || $json.tema || '' }}\nPost ID: {{ $json.post_id }}",
        [4680, 560]))

    # -- RECHAZAR --
    save_r = add(n_sheets_append("Guardar Rechazo", RECHAZOS_GID, "Rechazos", {
        "tema_id": "={{ $('Parsear Callback').first().json.tema_id }}",
        "motivo":  "rechazado_telegram_v2",
        "fecha":   "={{ $now.format('yyyy-MM-dd HH:mm') }}"
    }, [1560, 840]))
    tg_no  = add(n_tg("Telegram Rechazado ❌", CHAT_ID,
        "❌ Post rechazado. El tema queda disponible para la próxima generación.",
        [1820, 840]))

    # -- REGENERAR --
    save_reg = add(n_sheets_append("Guardar Regeneracion", RECHAZOS_GID, "Rechazos", {
        "tema_id": "={{ $('Parsear Callback').first().json.tema_id }}",
        "motivo":  "regenerado_telegram_v2",
        "fecha":   "={{ $now.format('yyyy-MM-dd HH:mm') }}"
    }, [1560, 1060]))
    call_gen = add(n_http("Trigger Nuevo Post", "POST",
        f"https://n8n.camiloayala.net/webhook/ma-writer-manual", [1820, 1060],
        body_json=json.dumps({"trigger": "regenerar_telegram"})
    ))
    tg_reg   = add(n_tg("Telegram Regenerando", CHAT_ID,
        "🔄 Regenerando post nuevo. Llega en 2-3 minutos con botones de aprobación.",
        [1820, 1180]))

    # ── CONEXIONES ────────────────────────────────────────────────────

    # Path A triggers → 3 sheet reads
    for trigger in [sched["name"], wh_man["name"]]:
        connect(conn, trigger, temas["name"])
        connect(conn, trigger, metr["name"])
        connect(conn, trigger, rech["name"])

    # 3 reads → merge (inputs 0, 1, 2)
    connect(conn, temas["name"],  merge["name"], inp=0)
    connect(conn, metr["name"],   merge["name"], inp=1)
    connect(conn, rech["name"],   merge["name"], inp=2)

    # Main pipeline Path A
    for a, b in [
        (merge, parse), (parse, prio), (prio, sp), (sp, ctx),
        (ctx, an1), (an1, outline), (outline, an2), (an2, draft),
        (draft, an3), (an3, final), (final, valid), (valid, ifq)
    ]:
        connect(conn, a["name"], b["name"])

    # Quality check: True → img, False → low quality notif
    connect(conn, ifq["name"],   img_s["name"], out=0)   # TRUE
    connect(conn, ifq["name"],   tg_low["name"], out=1)  # FALSE

    # Image strategy → both sources, then merge
    connect(conn, img_s["name"], uns["name"])
    connect(conn, img_s["name"], pol["name"])
    connect(conn, uns["name"],   img_f["name"])
    connect(conn, pol["name"],   img_f["name"])

    connect(conn, img_f["name"], tg_pre["name"])
    connect(conn, tg_pre["name"], save_w["name"])
    connect(conn, save_w["name"], tg_send["name"])

    # Path B: Telegram Entry → ACK + Parse (parallel)
    connect(conn, tg_wh["name"],    ack_tg["name"])
    connect(conn, tg_wh["name"],    cb_par["name"])
    connect(conn, cb_par["name"],   ans_cb["name"])
    connect(conn, ans_cb["name"],   upd_mkup["name"])
    connect(conn, upd_mkup["name"], router["name"])

    # Router: aprobar(0) → approve, rechazar(1) → reject, regenerar(2) → regenerate
    connect(conn, router["name"], lr_temas["name"],  out=0)
    connect(conn, router["name"], save_r["name"],    out=1)
    connect(conn, router["name"], save_reg["name"],  out=2)

    # Approve flow: read sheet → find row → check image
    connect(conn, lr_temas["name"], lr_fila["name"])
    connect(conn, lr_fila["name"],  if_img["name"])

    # Image path (TRUE): register asset → extract URL → download → prep binary → upload → prepare body
    connect(conn, if_img["name"],   reg_ast["name"],     out=0)
    connect(conn, reg_ast["name"],  extr_up["name"])
    connect(conn, extr_up["name"],  dl_img["name"])
    connect(conn, dl_img["name"],   prp_bin["name"])
    connect(conn, prp_bin["name"],  up_img["name"])
    connect(conn, up_img["name"],   prep_li_img["name"])
    connect(conn, prep_li_img["name"], pub_li["name"])

    # Text-only path (FALSE)
    connect(conn, if_img["name"],   prep_li["name"],     out=1)
    connect(conn, prep_li["name"],  pub_li["name"])

    # Shared publish chain
    connect(conn, pub_li["name"],   val_li["name"])
    connect(conn, val_li["name"],   reg_pub["name"])
    connect(conn, reg_pub["name"],  tg_ok["name"])

    # Reject flow
    connect(conn, save_r["name"],   tg_no["name"])

    # Regenerate flow: save to Rechazos → trigger new generation + notify Telegram (parallel)
    connect(conn, save_reg["name"], call_gen["name"])
    connect(conn, save_reg["name"], tg_reg["name"])

    return {
        "name": "[MA] WRITER — Motor 3 Pasos",
        "nodes": nodes,
        "connections": conn,
        "settings": {
            "executionOrder": "v1",
            "saveDataSuccessExecution": "all",
            "saveExecutionProgress": True,
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner"
        },
        "staticData": None
    }


if __name__ == "__main__":
    print("Construyendo [MA] WRITER — Motor 3 Pasos...")
    wf = build()
    print(f"  Nodos: {len(wf['nodes'])}")
    print(f"  Conexiones src: {len(wf['connections'])}")

    r = requests.post(f"{BASE_URL}/workflows", headers=HEADERS, json=wf, timeout=30)
    if r.status_code in (200, 201):
        d = r.json()
        wf_id = d.get("id", "?")
        print(f"  ✅ WRITER creado — ID: {wf_id}")
        print(f"  Webhook manual:  https://n8n.camiloayala.net/webhook/ma-writer-manual")
        print(f"  Webhook Telegram: https://n8n.camiloayala.net/webhook/ma-telegram-v2")
        print(f"  UI: https://n8n.camiloayala.net/workflow/{wf_id}")
    else:
        print(f"  ❌ Error {r.status_code}:")
        print(r.text[:600])
