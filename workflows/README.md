# Sistema Multi-Agente LinkedIn — Camilo Ayala

## Arquitectura

```
06:00 AM  [SCOUT]   Descubridor de Temas  → Google Sheets (Temas)
14:00     [WRITER]  Motor 3 Pasos         → Telegram → LinkedIn
23:00     [ANALYST] Métricas y Feedback   → Scores actualizados
```

## Workflows en N8N

| Agente | ID | Webhook Manual |
|---|---|---|
| WRITER | p71hf2LpPVg7vcSO | /webhook/ma-writer-manual |
| SCOUT  | dZCRLig1Ka4Rehei | /webhook/ma-scout-manual |
| ANALYST| cwAt7hnhFF8xY7Cn | /webhook/ma-analyst-manual |

## WRITER — Pipeline 3 Pasos

```
PASS 1: 🔍 Agente Analista  (Qwen 0.3) → Outline estratégico
          - Tensión central del tema
          - Ejemplo concreto de experiencia de Camilo
          - Creencia a contradecir
          - Postura no obvia + gancho exacto

PASS 2: ✍️ Agente Escritor   (Qwen 0.75) → Draft completo
          - Sigue el plan del Analista al pie de la letra
          - 1800-2500 chars, párrafos cortos

PASS 3: 🧹 Agente Humanizador (Qwen 0.4) → Elimina IA
          - Detecta frases de IA ("en el mundo actual", etc.)
          - Reescritura quirúrgica
          - Mantiene voz de Camilo
```

## SCOUT — Fuentes RSS (gratuitas)

- UX Design CC: https://uxdesign.cc/feed
- Fast Company Design: https://www.fastcompany.com/section/design/rss
- Medium Design Thinking: https://medium.com/feed/tag/design-thinking
- Harvard Business Review: https://hbr.org/resources/rss/articles
- IDEO Journal: https://ideo.com/journal.rss
- Medium Design Education: https://medium.com/feed/tag/design-education

Usa **Jina Reader** (r.jina.ai) para extraer texto limpio de cada artículo.

## ANALYST — Feedback Loop

1. Lee posts publicados (últimos 30 días)
2. Apify scraper → métricas LinkedIn (likes, comments, views)
3. Qwen analiza patrones por área/tono
4. Actualiza scores en Google Sheet automáticamente

## Telegram — Flujo de Aprobación

Al actualizar el webhook del bot Telegram a:
`https://n8n.camiloayala.net/webhook/ma-telegram-v2`

Los botones de aprobación funcionarán con el nuevo sistema.

Callback format: `v2|aprobar|{tema_id}` / `v2|rechazar|{tema_id}`

## Costo Total: $0

- Qwen 2.5:32b local (Ollama)
- Jina Reader: gratuito
- RSS feeds: gratuitos
- Pollinations AI: gratuito (imagen fallback)
- Google Sheets: gratuito
- Telegram Bot: gratuito
