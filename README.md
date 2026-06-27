# OSINTPassive

Sistema de inteligencia de fuentes abiertas (OSINT) multi-agente, construido con **LangGraph** y **Groq AI**. Dado un email, dominio o nombre de usuario, lanza en paralelo varios agentes que rastrean presencia digital, brechas de datos, perfiles en plataformas y snapshots históricos, y genera un informe de inteligencia estructurado con IA.

---

## Características

- **7 agentes en paralelo** orquestados con LangGraph
- **LLM gratuito** via Groq — modelo `llama-3.3-70b-versatile`, sin coste
- **Dos interfaces**: app web con Streamlit y CLI con Rich
- **Streaming en tiempo real**: la UI muestra el progreso agente por agente
- **Deduplicación automática** de emails y URLs (limpia parámetros de tracking)
- **Backoff exponencial** en peticiones HTTP — reintentos ante rate limits y timeouts
- **127 tests** con pytest-asyncio

---

## Agentes

| Agente | Fuente | Qué hace |
|---|---|---|
| `validator_node` | — | Limpia y clasifica el input (email / dominio / usuario) |
| `github_agent` | GitHub API | Extrae emails expuestos en commits públicos |
| `dork_agent` | DuckDuckGo | Lanza búsquedas OSINT adaptadas al tipo de input |
| `alias_agent` | 10 plataformas | Verifica existencia de perfil (GitHub, Reddit, Telegram, etc.) |
| `wayback_agent` | Wayback Machine | Obtiene el snapshot más reciente y el más antiguo |
| `breach_agent` | LeakCheck.io | Comprueba si el email aparece en brechas de datos conocidas |
| `analyst_agent` | Groq LLM | Genera informe con resumen, alertas y nivel de criticidad |

---

## Arquitectura del grafo

```
START
  │
  ▼
validator_node
  │
  ├──────────────────────┐──────────────────────┐
  ▼                      ▼                      ▼
github_agent          dork_agent           alias_agent
  │                      │                      │
  └──────────┬───────────┘──────────┬───────────┘
             ▼                      ▼
        wayback_agent          breach_agent
             │                      │
             └──────────┬───────────┘
                        ▼
                  analyst_agent
                        │
                       END
```

---

## Requisitos

- Python 3.11 o superior
- Cuenta gratuita en [Groq](https://console.groq.com) para obtener la API key

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/herjflorez/Proyecto-OSINT---Hernando-Florez.git
cd Proyecto-OSINT---Hernando-Florez
```

### 2. Crear y activar el entorno virtual

```bash
# Crear el entorno
python -m venv .venv

# Activar en Windows
.\.venv\Scripts\Activate.ps1

# Activar en macOS / Linux
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar la API key de Groq

Copia el archivo de ejemplo y añade tu key:

```bash
cp .env.example .env
```

Edita `.env`:

```
GROQ_API_KEY=tu_api_key_de_groq_aqui
GROQ_MODEL=llama-3.3-70b-versatile
```

> **Obtener la key gratis:** regístrate en [console.groq.com](https://console.groq.com) → *API Keys* → *Create API Key*. El tier gratuito es suficiente para uso normal.

---

## Uso

### Aplicación web (Streamlit)

```bash
streamlit run ui/app.py
```

Se abre automáticamente en `http://localhost:8501`. Introduce un email, dominio o nombre de usuario y pulsa **Investigar**. La UI muestra en tiempo real qué agente está ejecutándose y qué ha encontrado.

### Interfaz de línea de comandos (CLI)

```bash
python main.py
```

Introduce el objetivo cuando se solicite. Los resultados se muestran con tablas y colores en la terminal.

---

## Estructura del proyecto

```
├── config/
│   └── settings.py          # Carga variables de entorno
├── core/
│   ├── agents/
│   │   ├── base_agent.py    # fetch_with_retry — HTTP con backoff exponencial
│   │   ├── github_agent.py
│   │   ├── dork_agent.py
│   │   ├── alias_agent.py
│   │   ├── wayback_agent.py
│   │   ├── breach_agent.py
│   │   └── analyst_agent.py
│   ├── graph.py             # Construccion del grafo LangGraph
│   ├── runner.py            # Streaming de eventos para la UI
│   ├── state.py             # OSINTState + reducers de deduplicacion
│   └── validator.py         # Clasificacion y limpieza del input
├── ui/
│   ├── app.py               # Interfaz web Streamlit
│   └── cli.py               # Interfaz CLI con Rich
├── utils/
│   └── cache.py             # Cache async con diskcache
├── tests/                   # 127 tests con pytest-asyncio
├── main.py                  # Punto de entrada CLI
├── requirements.txt
├── pytest.ini
└── .env.example
```

---

## Tests

```bash
pytest
```

Salida esperada: `127 passed`.

---

## Aviso legal

Esta herramienta está diseñada para investigación de seguridad, auditorías de exposición digital propia y propósitos educativos. El usuario es responsable de asegurarse de que su uso cumple con la legislación aplicable y con los términos de servicio de las plataformas consultadas.
