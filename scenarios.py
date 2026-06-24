"""
scenarios.py — Scenario definitions for the Concurrent Gemma demo.

This is a faithful port of the original Google Gemma Cookbook concurrent app,
adapted for local Ollama + Gradio on Windows with NVIDIA RTX hardware in mind.

Core ideas preserved:
- Orchestrator plans specific work for each agent
- Specialists work truly in parallel
- Each scenario has its own visual personality and output format
- Easy to add new scenarios

Live cards (during generation) and final gallery both use Tailwind via CDN
so the visual language stays consistent with the original demo.
"""

import html


# ─── Palettes (kept from original) ─────────────────────────────────────────────

_COLORS = [
    "1;35", "1;36", "1;33", "1;32", "1;34", "0;36", "0;35", "0;33", "0;32", "0;34",
    "1;31", "0;31", "1;37", "0;37", "1;35", "1;36", "1;33", "1;32", "1;34", "0;36",
]

_LANG_EMOJIS = [
    "🇫🇷", "🇪🇸", "🇩🇪", "🇯🇵", "🇨🇳", "🇰🇷", "🇸🇦", "🇮🇳", "🇧🇷", "🇷🇺",
    "🇮🇹", "🇹🇷", "🇻🇳", "🇹🇭", "🇳🇱", "🇵🇱", "🇸🇪", "🇬🇷", "🇮🇩", "🇺🇦",
]

_LANG_NAMES = [
    "french", "spanish", "german", "japanese", "chinese", "korean",
    "arabic", "hindi", "portuguese", "russian", "italian", "turkish",
    "vietnamese", "thai", "dutch", "polish", "swedish", "greek",
    "indonesian", "ukrainian",
]

_SVG_STYLES = [
    "minimalist", "cyberpunk", "watercolor", "pixel art",
    "abstract", "geometric", "neon", "vintage",
    "pop art", "isometric", "steampunk", "monochrome",
    "low poly", "surreal", "line art", "flat design",
    "3D render", "anime", "cubism", "synthwave",
]

_CODE_LANGS = [
    "python", "javascript", "rust", "go", "c", "java", "ruby", "swift",
    "kotlin", "typescript", "php", "scala", "haskell", "elixir",
    "lua", "perl", "r", "julia", "dart", "zig",
]

_CODE_EMOJIS = [
    "🐍", "📜", "🦀", "🐹", "⚙️", "☕", "💎", "🍎",
    "🟣", "🔷", "🐘", "🔴", "λ", "💧",
    "🌙", "🐪", "📊", "🔮", "🎯", "⚡",
]


# ─── Agent Factories ───────────────────────────────────────────────────────────

def make_translate_agents(n: int = 4) -> list[dict]:
    return [
        {
            "name": _LANG_NAMES[i % len(_LANG_NAMES)],
            "emoji": _LANG_EMOJIS[i % len(_LANG_EMOJIS)],
            "color": _COLORS[i % len(_COLORS)],
            "direct_instruction": f"Translate this into {_LANG_NAMES[i % len(_LANG_NAMES)]}: {{topic}}",
        }
        for i in range(n)
    ]


def make_svg_agents(n: int = 4) -> list[dict]:
    return [
        {
            "name": f"Agent {i+1}",
            "emoji": "🎨",
            "color": _COLORS[i % len(_COLORS)],
            "direct_instruction": (
                f"Draw a simple SVG of a {{topic}}. "
                f"Use a {_SVG_STYLES[i % len(_SVG_STYLES)]} style. "
                f"Output SVG only and start with <svg"
            ),
        }
        for i in range(n)
    ]


def make_code_agents(n: int = 4) -> list[dict]:
    return [
        {
            "name": _CODE_LANGS[i % len(_CODE_LANGS)],
            "emoji": _CODE_EMOJIS[i % len(_CODE_EMOJIS)],
            "color": _COLORS[i % len(_COLORS)],
            "direct_instruction": f"Write a solution for {{topic}} in {_CODE_LANGS[i % len(_CODE_LANGS)]}. Output ONLY code.",
        }
        for i in range(n)
    ]


def make_ascii_agents(n: int = 4) -> list[dict]:
    return [
        {
            "name": f"Agent {i+1}",
            "emoji": "👾",
            "color": _COLORS[i % len(_COLORS)],
            "direct_instruction": (
                f"Create ASCII art of {{topic}}. "
                f"Output ASCII art only."
            ),
        }
        for i in range(n)
    ]


_EXPLANATION_STYLES = [
    "to a curious 5-year-old using simple analogies",
    "to a high school student with clear examples",
    "to a college professor using precise terminology",
    "like a poet using vivid metaphors and imagery",
    "as a programmer using step-by-step logic and pseudocode",
    "to a skeptical journalist with evidence and caveats",
]

def make_explanations_agents(n: int = 4) -> list[dict]:
    return [
        {
            "name": f"Explainer {i+1}",
            "emoji": "🧠",
            "color": _COLORS[i % len(_COLORS)],
            "direct_instruction": f"Explain {{topic}} {_EXPLANATION_STYLES[i % len(_EXPLANATION_STYLES)]}.",
        }
        for i in range(n)
    ]


# ─── System Prompts ────────────────────────────────────────────────────────────

TRANSLATE_SYSTEM = (
    "You are a translator. Output ONLY the translated text. "
    "No explanations, no preamble, no original text, no quotes."
)

SVG_SYSTEM = (
    "You are an expert at drawing simple recursive fractals in SVG. Output ONLY a valid raw <svg> tag with viewBox='0 0 120 120'. "
    "Focus on fractal patterns (Sierpinski, Koch curve, tree, dragon, or similar recursive structures) using ONLY basic shapes and recursion-like repetition. "
    "Use clean lines, limited colors (2-4), and geometric beauty. No text. No markdown. Start with <svg and end with </svg>."
)

CODE_SYSTEM = (
    "You are a skilled programmer. Output ONLY clean, working code. "
    "No explanations, no markdown fences, no comments unless essential for the code itself. "
    "Raw code only. Make it correct and reasonably efficient."
)

ASCII_SYSTEM = (
    "You are an ASCII artist. Output ONLY raw ASCII art. "
    "No explanations, no markdown fences, no text before or after the art."
)

EXPLANATIONS_SYSTEM = (
    "You are an excellent teacher and communicator. "
    "Explain the topic clearly and engagingly in the exact style requested. "
    "Use short paragraphs, good structure, and helpful examples. "
    "Output ONLY the explanation text. No introductions, no summaries, no meta comments."
)


# ─── Planning Prompts ──────────────────────────────────────────────────────────

TRANSLATE_PLAN = {
    "system": (
        'Output a JSON array with {n_agents} objects. Each has "name" and "instruction". '
        "Keep each instruction to ONE sentence. Output ONLY valid JSON."
    ),
    "user": (
        'Translate this into {n_agents} languages: "{topic}"\n'
        "Agents: {agent_list}\n"
        'Each instruction: "Translate into [language]: [text]". That is all.'
    ),
}

SVG_PLAN = {
    "system": (
        'Output a JSON array with {n_agents} objects. Each has "name", "instruction", and "label". '
        'The "label" is a short title. Output ONLY valid JSON.'
    ),
    "user": (
        'Theme: "{topic}". Agents: {agent_list}\n'
        'Each instruction: "Draw a simple recursive fractal pattern inspired by [one aspect of the theme] using basic shapes and repetition." '
        "Focus on fractal structure and symmetry. Keep it clean."
    ),
}

CODE_PLAN = {
    "system": (
        'Output a JSON array with {n_agents} objects. Each has "name" and "instruction". '
        "Keep each instruction to ONE sentence. Output ONLY valid JSON."
    ),
    "user": (
        'Task: "{topic}". Agents (each is a programming language): {agent_list}\n'
        'Each instruction: "Write a clean implementation of [the task] in [language].". One sentence. That is all.'
    ),
}

ASCII_PLAN = {
    "system": (
        'Output a JSON array with {n_agents} objects. Each has "name", "instruction", and "label". '
        'The "label" is a one word description of the ASCII art (e.g. "Cat"). '
        "Output ONLY valid JSON."
    ),
    "user": (
        'Theme: "{topic}". Agents (each is an ASCII artist): {agent_list}\n'
        'Each instruction: "Create realistic and small ASCII (max 20x60 characters) art of [specific aspect of the theme - one word description only]". '
        'One sentence. That is all. '
    ),
}

EXPLANATIONS_PLAN = {
    "system": (
        'Output a JSON array with {n_agents} objects. Each has "name", "instruction", and "label". '
        'The "label" is a short style descriptor (e.g. "For a 5-year-old"). '
        "Output ONLY valid JSON."
    ),
    "user": (
        'Topic: "{topic}". Explain it in {n_agents} different styles for these audiences: {agent_list}\n'
        'Each instruction: "Explain the topic [specific style]". Keep it concise but clear. One sentence max.'
    ),
}


# ─── Card Renderers (for FINAL gallery) ────────────────────────────────────────

def translate_card(agent, result, task=None):
    name = agent["name"]
    emoji = agent["emoji"]
    text = result.strip().strip("`").strip()
    return (
        f'<div class="flex items-center gap-2 mb-3">\n'
        f'    <span class="text-xl">{emoji}</span>\n'
        f'    <span class="text-xs font-semibold text-gray-400 uppercase tracking-wider">{name}</span>\n'
        f'</div>\n'
        f'<div class="text-sm text-gray-700 leading-relaxed">{text}</div>'
    )


def svg_card(agent, result, task=None):
    name = agent["name"]
    label = task.get("label", name.title()) if task else name.title()
    svg = result
    if "<svg" in svg:
        start = svg.index("<svg")
        end = svg.index("</svg>") + 6 if "</svg>" in svg else len(svg)
        svg = svg[start:end]
    else:
        svg = '<div class="text-sm text-gray-400 p-4 text-center">Failed to generate SVG</div>'
    return (
        f'<div class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">{name}</div>\n'
        f'<div class="w-full aspect-square flex items-center justify-center p-2">{svg}</div>\n'
        f'<div class="text-sm font-semibold text-gray-500 mt-3 pt-3 border-t border-gray-200 w-full text-center">{label}</div>'
    )


def code_card(agent, result, task=None):
    name = agent["name"]
    emoji = agent.get("emoji", "💻")
    code = result.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines)
    escaped = html.escape(code)
    lang_class = f'language-{name}' if name in _CODE_LANGS else ''
    return (
        f'<div class="flex items-center gap-2 px-1 pb-3 mb-3 border-b border-gray-200">\n'
        f'    <span class="text-lg">{emoji}</span>\n'
        f'    <span class="text-xs font-semibold text-gray-500 uppercase tracking-wider">{name}</span>\n'
        f'</div>\n'
        f'<pre class="m-0 text-xs leading-relaxed overflow-auto"><code class="{lang_class}" style="padding: 0; background: transparent;">{escaped}</code></pre>'
    )


def ascii_card(agent, result, task=None):
    name = agent["name"]
    label = task.get("label", name.title()) if task else name.title()
    art = result
    if art.startswith("```"):
        lines = art.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        art = "\n".join(lines)
    art = art.strip("\n")
    escaped = html.escape(art)
    return (
        f'<div class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">{name}</div>\n'
        f'<div class="w-full bg-gray-900 rounded-lg p-4 flex items-center justify-center min-h-[180px] overflow-auto">\n'
        f'    <pre class="text-base font-mono text-green-400 leading-tight" style="text-shadow: 0 0 5px rgba(74, 222, 128, 0.5);">{escaped}</pre>\n'
        f'</div>\n'
        f'<div class="text-sm font-semibold text-gray-500 mt-3 pt-3 border-t border-gray-200 w-full text-center">{label}</div>'
    )


def explanations_card(agent, result, task=None):
    name = agent["name"]
    style = task.get("label", name) if task else name
    text = result.strip()
    return (
        f'<div class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">{style}</div>\n'
        f'<div class="text-sm text-gray-200 leading-relaxed">{text}</div>'
    )


# ─── LIVE agent card renderer (Tailwind, dark-friendly for Windows) ────────────

def live_agent_card(agent: dict, status: str, partial_text: str, tps: float, tokens: int) -> str:
    """
    Matrix-style card: pure black bg, matrix green text, white labels.
    """
    name = agent.get("name", "Agent")
    emoji = agent.get("emoji", "🤖")
    display_name = name.upper().replace("_", " ")[:12]

    status_map = {
        "waiting": ("WAIT", "#888888"),
        "running": ("LIVE", "#00ff41"),
        "done": ("DONE", "#ffffff"),
        "error": ("ERR", "#ff4444"),
    }
    status_label, status_col = status_map.get(status, ("...", "#888888"))

    shown = partial_text.strip()
    if len(shown) > 380:
        shown = shown[:380] + "…"

    escaped = html.escape(shown).replace("\n", "<br>")

    tps_str = f"{tps:.1f}" if tps > 0 else "--"
    tokens_str = str(tokens) if tokens else "0"

    return f"""
<div style="background:#000000; border:1px solid #00ff41; padding:6px; font-family:monospace; font-size:10px; color:#00ff41; min-height:130px; display:flex; flex-direction:column;">
  <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #00ff41; padding-bottom:2px; margin-bottom:3px; color:#ffffff; font-size:9px;">
    <span>{emoji} {display_name}</span>
    <span style="color:{status_col}; font-weight:bold;">{status_label}</span>
  </div>
  <div style="flex:1; overflow:auto; font-size:9px; line-height:1.2; color:#00ff41; background:#000; padding:2px;">
    {escaped or '<span style="color:#555;">waiting...</span>'}
  </div>
  <div style="font-size:8px; color:#ffffff; margin-top:3px; display:flex; justify-content:space-between;">
    <span>⚡{tps_str}t/s</span><span>{tokens_str}t</span>
  </div>
</div>
"""


# ─── Page Builder for FINAL results (from original, lightly cleaned) ───────────

def build_page(topic, scenario, results, tasks=None):
    """Build the full Tailwind HTML gallery page (used for final results)."""
    agents = scenario["agents"]
    title = scenario["title"]
    render_card = scenario["render_card"]
    extra_head = scenario.get("extra_head", "")
    extra_body = scenario.get("extra_body", "")

    cols = min((len(agents) + 1) // 2, 5)

    task_map = {}
    if tasks:
        for t in tasks:
            task_map[t.get("name", "")] = t

    cards_html = []
    for agent in agents:
        result = results.get(agent["name"], "")
        task = task_map.get(agent["name"])
        inner = render_card(agent, result, task)
        cards_html.append(
            f'            <div class="card">\n{inner}\n            </div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ background:#000; color:#00ff41; font-family:monospace; margin:4px; font-size:12px; }}
        .card {{ background:#000; border:1px solid #00ff41; padding:6px; }}
        h1 {{ color:#fff; font-size:16px; margin:0; }}
        svg {{ max-width:100%; }}
    </style>
{extra_head}
</head>
<body>
<div style="max-width:100%; margin:auto;">
  <div style="border-bottom:1px solid #00ff41; padding-bottom:3px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:baseline;">
    <div><h1>{title}</h1><span style="color:#fff; font-size:9px;">MATRIX MODE</span></div>
    <div style="font-size:10px; color:#fff;">{topic}</div>
  </div>
  <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(200px,1fr)); gap:4px;">
{chr(10).join(cards_html)}
  </div>
  <div style="text-align:center; margin-top:6px; font-size:9px; color:#555;">{len(agents)} AGENTS</div>
</div>
{extra_body}
</body>
</html>"""


# ─── Scenario Registry ─────────────────────────────────────────────────────────

SCENARIOS = {
    "translate": {
        "make_agents": make_translate_agents,
        "plan": TRANSLATE_PLAN,
        "system_prompt": TRANSLATE_SYSTEM,
        "render_card": translate_card,
        "title": "Translation Grid",
        "default_n": 4,
    },
    "fractals": {
        "make_agents": make_svg_agents,
        "plan": SVG_PLAN,
        "system_prompt": SVG_SYSTEM,
        "render_card": svg_card,
        "title": "Fractal Gallery",
        "default_n": 4,
    },
    "code": {
        "make_agents": make_code_agents,
        "plan": CODE_PLAN,
        "system_prompt": CODE_SYSTEM,
        "render_card": code_card,
        "title": "Code Gallery",
        "default_n": 4,
    },
    "ascii": {
        "make_agents": make_ascii_agents,
        "plan": ASCII_PLAN,
        "system_prompt": ASCII_SYSTEM,
        "render_card": ascii_card,
        "title": "ASCII Art Gallery",
        "default_n": 4,
    },
    "explanations": {
        "make_agents": make_explanations_agents,
        "plan": EXPLANATIONS_PLAN,
        "system_prompt": EXPLANATIONS_SYSTEM,
        "render_card": explanations_card,
        "title": "Multiple Explanations",
        "default_n": 4,
    },
}


def get_scenario(name: str, n_agents: int = None) -> dict:
    """Get a scenario by name. Generates agents dynamically."""
    if name not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise KeyError(f"Unknown scenario '{name}'. Available: {available}")

    scenario = dict(SCENARIOS[name])
    n = n_agents or scenario.get("default_n", 4)
    scenario["agents"] = scenario["make_agents"](n)

    # Inject n_agents into plan strings
    plan = scenario["plan"]
    scenario["plan"] = {
        k: v.replace("{n_agents}", str(n)) if isinstance(v, str) else v
        for k, v in plan.items()
    }
    return scenario
