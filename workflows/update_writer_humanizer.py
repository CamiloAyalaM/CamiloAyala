#!/usr/bin/env python3
"""
update_writer_humanizer.py
Mejora el Humanizador de [MA] WRITER con few-shot examples reales:
  - Agrega nodo "Extraer Ejemplos Top ER" entre Parsear Draft y Agente Humanizador
  - Lee top-2 posts por engagement_rate del histórico (desde Parsear Sheets)
  - Inyecta esos posts como ejemplos de referencia en el prompt del Humanizador
  - El Humanizador ahora usa el estilo REAL de Camilo, no solo la descripción del perfil
"""
import json, uuid, requests

API_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0YmY4ODRkNC1hMGUxLTRiNjgtOTVlZC1kMDc0ZWY5N2ExZDQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOWY0MWY5OWQtZDNkNy00NWNjLWFkZjAtZjc2ZmMwZDQxZjcyIiwiaWF0IjoxNzcxNzcyMzg4fQ.RmQl5yX4T9pAUn4swhvMcydMv-8VukNnlbPc7NgbK0U"
BASE_URL = "https://n8n.camiloayala.net/api/v1"
HEADERS  = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}
WRITER_ID= "p71hf2LpPVg7vcSO"

def nid(): return str(uuid.uuid4())

# ── Nodo nuevo: extrae los top-2 posts reales de Camilo por ER ──────────

CODE_EXTRAER_EJEMPLOS = r'''
// Lee el historial ya cargado desde Parsear Sheets (dentro del mismo workflow)
const parsed = $('Parsear Sheets').first().json;
const temas    = parsed.temas    || [];
const metricas = parsed.metricas || [];

// Build ER map: post_id → max ER
const erMap = {};
metricas.forEach(m => {
  const er = parseFloat(m.engagement_rate) || 0;
  if (!erMap[m.post_id] || er > erMap[m.post_id]) erMap[m.post_id] = er;
});

// Find published temas that have post_text stored and an ER record
const con_texto = temas
  .filter(t => t.estado === 'publicado' && t.post_text && t.post_id && erMap[t.post_id])
  .map(t => ({ ...t, best_er: erMap[t.post_id] }))
  .sort((a, b) => b.best_er - a.best_er)
  .slice(0, 2);

let ejemplos_str = '';
if (con_texto.length > 0) {
  ejemplos_str = '\n\nEJEMPLOS REALES DE POSTS DE CAMILO CON ALTO ENGAGEMENT:\n';
  ejemplos_str += '(Usa estos como referencia del TONO y RITMO — no copies frases)\n';
  con_texto.forEach((p, i) => {
    const er_pct = (p.best_er * 100).toFixed(2);
    ejemplos_str += `\n[EJEMPLO ${i + 1} — ER real: ${er_pct}%]\n`;
    ejemplos_str += p.post_text.trim();
    ejemplos_str += `\n[FIN EJEMPLO ${i + 1}]\n`;
  });
}

// Pass through everything from Parsear Draft, just adding the examples
const prev = $('Parsear Draft').first().json;
return [{ json: { ...prev, ejemplos_humanizador: ejemplos_str } }];
'''

# ── Prompt del Humanizador actualizado (añade los ejemplos reales) ────────

PROMPT_HUMANIZADOR_ACTUALIZADO = (
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
    "{{ $json.ejemplos_humanizador }}\n\n"
    "Devuelve el mismo JSON con post_text humanizado (sin backticks):\n"
    '{"post_text":"texto humanizado","hook_type":"mismo valor","imagen_descripcion":"mismo valor","hashtags":["mismos","hashtags"]}'
)

def patch_writer():
    # 1. GET current WRITER workflow
    r = requests.get(f"{BASE_URL}/workflows/{WRITER_ID}", headers=HEADERS, timeout=15)
    if r.status_code != 200:
        print(f"  ❌ No se pudo obtener WRITER: {r.status_code}")
        return
    wf = r.json()
    nodes = wf.get("nodes", [])
    conn  = wf.get("connections", {})

    # 2. Find key nodes by name
    node_by_name = {n["name"]: n for n in nodes}
    draft_node   = node_by_name.get("Parsear Draft")
    human_node   = node_by_name.get("🧹 Agente Humanizador")

    if not draft_node or not human_node:
        print("  ❌ No se encontraron los nodos 'Parsear Draft' o '🧹 Agente Humanizador'")
        print(f"  Nodos existentes: {[n['name'] for n in nodes]}")
        return

    # 3. Determine positions
    draft_pos = draft_node.get("position", [2600, 0])
    human_pos = human_node.get("position", [2860, 0])

    # New node sits between them
    nuevo_pos = [
        (draft_pos[0] + human_pos[0]) // 2,
        draft_pos[1]
    ]

    # 4. Build new node
    nuevo_nodo = {
        "id":   nid(),
        "name": "Extraer Ejemplos Top ER",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": nuevo_pos,
        "parameters": {"jsCode": CODE_EXTRAER_EJEMPLOS}
    }
    nodes.append(nuevo_nodo)

    # 5. Update Humanizer prompt (user message)
    for node in nodes:
        if node["name"] == "🧹 Agente Humanizador":
            msgs = node.get("parameters", {}).get("messages", {}).get("values", [])
            for msg in msgs:
                if msg.get("role") != "system":
                    msg["content"] = PROMPT_HUMANIZADOR_ACTUALIZADO
            break

    # 6. Update connections:
    #    Remove: Parsear Draft → 🧹 Agente Humanizador
    #    Add:    Parsear Draft → Extraer Ejemplos Top ER → 🧹 Agente Humanizador
    draft_name  = draft_node["name"]
    human_name  = human_node["name"]
    nuevo_name  = nuevo_nodo["name"]

    if draft_name in conn:
        for output_list in conn[draft_name].get("main", []):
            # Remove direct connection to Humanizer
            output_list[:] = [
                c for c in output_list
                if c.get("node") != human_name
            ]
            # Add connection to new node if not already there
            if not any(c.get("node") == nuevo_name for c in output_list):
                output_list.append({"node": nuevo_name, "type": "main", "index": 0})

    # Add: nuevo_nodo → 🧹 Agente Humanizador
    if nuevo_name not in conn:
        conn[nuevo_name] = {"main": []}
    if not conn[nuevo_name]["main"]:
        conn[nuevo_name]["main"].append([])
    conn[nuevo_name]["main"][0].append({"node": human_name, "type": "main", "index": 0})

    # 7. PUT updated workflow back (only mutable fields accepted by N8N API)
    payload = {
        "name":        wf.get("name"),
        "nodes":       nodes,
        "connections": conn,
        "settings":    wf.get("settings", {}),
        "staticData":  wf.get("staticData")
    }

    ru = requests.put(
        f"{BASE_URL}/workflows/{WRITER_ID}",
        headers=HEADERS,
        json=payload,
        timeout=30
    )
    if ru.status_code in (200, 201):
        print(f"  ✅ WRITER Humanizador actualizado — ID: {WRITER_ID}")
        print(f"  Nodo agregado: '{nuevo_name}' en posición {nuevo_pos}")
        # Re-activate
        ra = requests.post(
            f"{BASE_URL}/workflows/{WRITER_ID}/activate",
            headers=HEADERS,
            timeout=10
        )
        print(f"  Activar: {ra.status_code}")
    else:
        print(f"  ❌ Error {ru.status_code}: {ru.text[:500]}")


if __name__ == "__main__":
    print("Mejorando Humanizador de [MA] WRITER con few-shot examples...")
    patch_writer()
