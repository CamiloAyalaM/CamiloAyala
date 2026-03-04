# [MA] REPORTER — Setup Guide

## 1. Carpeta Google Drive

Crea una carpeta llamada **"LinkedIn Reports"** en tu Google Drive.
Cada vez que descargues un informe de LinkedIn, suéltalo ahí.

---

## 2. Google Sheet — Estructura requerida

Crea un Sheet con **dos pestañas**:

### Pestaña: `Rendimiento Posts`
| Columna | Tipo | Descripción |
|---|---|---|
| archivo | Texto | Nombre del archivo CSV fuente |
| post_id | Texto | ID único del post (de la URL o nombre del archivo) |
| fecha_publicacion | Fecha | Cuándo se publicó el post |
| tipo | Texto | Tipo de contenido (Text, Image, Video, Document…) |
| contenido_preview | Texto | Primeros 200 caracteres del post |
| impresiones | Número | Total de vistas (incluyendo repetidas) |
| vistas_unicas | Número | Personas únicas que vieron el post |
| clics | Número | Clics en el contenido o CTA |
| likes | Número | Reacciones totales |
| comentarios | Número | Comentarios |
| compartidos | Número | Reposts/compartidos |
| nuevos_seguidores | Número | Seguidores ganados por este post |
| ctr | Número | Click-through rate (%) |
| engagement_rate | Número | ER total (%) |
| total_interacciones | Número | likes + comentarios + compartidos + clics |
| fecha_importacion | Fecha | Cuándo se indexó en el sistema |

### Pestaña: `Demografía Posts`
| Columna | Tipo | Descripción |
|---|---|---|
| archivo | Texto | Nombre del archivo CSV fuente |
| post_id | Texto | ID del post al que corresponde |
| categoria | Texto | Tipo de dato: Función laboral / Industria / Senioridad / Ubicación / Tamaño de empresa |
| segmento | Texto | Valor específico (ej: "Marketing", "Senior", "Colombia") |
| porcentaje | Número | % de la audiencia que corresponde a este segmento |
| fecha_importacion | Fecha | Cuándo se indexó |

---

## 3. Configurar el workflow en n8n

Reemplaza estos valores en el JSON antes de importar:

| Placeholder | Reemplazar con |
|---|---|
| `TU_GOOGLE_SHEET_ID` | El ID de tu Google Sheet (está en la URL: `.../spreadsheets/d/ID/edit`) |
| `TU_TELEGRAM_CHAT_ID` | Tu Chat ID de Telegram |
| `LinkedIn Reports` | El nombre exacto de tu carpeta en Drive |

---

## 4. Cómo descargar los informes de LinkedIn

1. Ve a tu post en LinkedIn
2. Clic en "Estadísticas" (ícono de gráfico)
3. Clic en "Exportar estadísticas" → selecciona rango de fechas
4. Descarga el CSV
5. Renómbralo si quieres (el sistema detecta el post_id del nombre si tiene formato `PostAnalytics_Nombre_ID.csv`)
6. Sube a la carpeta **"LinkedIn Reports"** de Google Drive
7. El workflow se activa automáticamente y en ~30s recibes confirmación en Telegram

---

## 5. Columnas detectadas automáticamente

El parser detecta estas variaciones de nombres (inglés y español):

**Performance:**
- `Impressions` / `Views` / `Impresiones` / `Vistas`
- `Clicks` / `Clics`
- `Likes` / `Me gusta` / `Reactions`
- `Comments` / `Comentarios`
- `Reposts` / `Shares` / `Compartidos`
- `Follows` / `Seguidores nuevos`
- `CTR` / `Click through rate`

**Demografía:** Detectada por palabras clave en el header de cada sección del CSV.
