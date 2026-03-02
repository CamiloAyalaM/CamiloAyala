# Sistema Multi-Agente LinkedIn — Camilo Ayala

## Arquitectura (v2.1)

```
06:00 AM  [SCOUT]   Descubridor de Temas  → Google Sheets (Temas)
14:00     [WRITER]  Motor 3 Pasos         → Telegram → LinkedIn
23:00     [ANALYST] Métricas y Feedback   → Scores actualizados → llama FEEDBACK
07:00 DOM [FEEDBACK] Ciclo de Aprendizaje → Scores globales + informe semanal
```

## Workflows en N8N

| Agente   | ID                 | Webhook Manual               | Cron              |
|----------|--------------------|------------------------------|-------------------|
| WRITER   | p71hf2LpPVg7vcSO   | /webhook/ma-writer-manual    | L/X/V 14:00       |
| SCOUT    | dZCRLig1Ka4Rehei   | /webhook/ma-scout-manual     | Diario 06:00      |
| ANALYST  | cwAt7hnhFF8xY7Cn   | /webhook/ma-analyst-manual   | L/X/V 23:00       |
| FEEDBACK | 6kNsqFSBI5DpCrW1   | /webhook/ma-feedback-manual  | Domingo 07:00     |

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

        [Extraer Ejemplos Top ER] — Lee top-2 posts reales por ER del Sheet
          - Inyecta estilos reales de Camilo como referencia

PASS 3: 🧹 Agente Humanizador (Qwen 0.4) → Elimina IA
          - Few-shot: usa posts reales de alto engagement como referencia
          - Detecta frases de IA ("en el mundo actual", etc.)
          - Reescritura quirúrgica mantiene voz de Camilo
```

## SCOUT — Fuentes RSS (gratuitas)

- UX Design CC: https://uxdesign.cc/feed
- Fast Company Design: https://www.fastcompany.com/section/design/rss
- Medium Design Thinking: https://medium.com/feed/tag/design-thinking
- Harvard Business Review: https://hbr.org/resources/rss/articles
- IDEO Journal: https://ideo.com/journal.rss
- Medium Design Education: https://medium.com/feed/tag/design-education

Usa **Jina Reader** (r.jina.ai) para extraer texto limpio de cada artículo.

## ANALYST v2 — Métricas sin Apify

1. Lee posts publicados (últimos 45 días) desde Temas Sheet
2. **LinkedIn ugcPosts API** (Bearer token existente, cero costo) → stats actuales
3. Fallback: datos históricos del Sheet Metricas si API no retorna engagement
4. **Detectar Outliers**: posts con ER > 2× mediana reciben notificación
5. Qwen analiza patrones por área/tono
6. Actualiza scores en Google Sheet automáticamente
7. Llama webhook de FEEDBACK al finalizar

## FEEDBACK — Ciclo de Aprendizaje Semanal

Corre domingos o cuando es llamado por ANALYST:
1. Lee Temas + Metricas completos
2. Calcula correlaciones: ER por área / tono / tipo_post
3. Detecta posts estrella (outliers positivos)
4. Qwen genera estrategia para el ciclo siguiente
5. Actualiza scores globales con factores de rendimiento real
6. Envía informe semanal a Telegram
7. Responde al webhook de ANALYST con los insights (JSON)

## Telegram — Flujo de Aprobación

Webhook del bot: `https://n8n.camiloayala.net/webhook/ma-telegram-v2`

Callback format: `v2|aprobar|{tema_id}` / `v2|rechazar|{tema_id}` / `v2|regenerar|{tema_id}`

## Scripts de Build / Update

| Script                          | Función                                    |
|---------------------------------|--------------------------------------------|
| `build_writer.py`               | Crea WRITER desde cero                     |
| `build_scout.py`                | Crea SCOUT desde cero                      |
| `build_analyst.py`              | Crea ANALYST (versión original con Apify)  |
| `update_analyst_v2.py`          | Actualiza ANALYST → LinkedIn API (v2)      |
| `build_feedback.py`             | Crea FEEDBACK (Ciclo de Aprendizaje)       |
| `update_writer_humanizer.py`    | Agrega few-shot examples al Humanizador    |

## Costo Total: $0

- Qwen 2.5:32b local (Ollama) — LLM
- LinkedIn ugcPosts API — métricas (token existente de publicación)
- Jina Reader (r.jina.ai) — extracción de artículos
- RSS feeds — descubrimiento de temas
- Unsplash API — imágenes (free tier)
- Picsum Photos — fallback de imágenes
- Google Sheets — almacenamiento
- Telegram Bot — aprobaciones y reportes
