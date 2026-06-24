"""
app.py — Concurrent Gemma Gradio Dashboard (NVIDIA / Windows RTX edition)

A local-first, dark, Tailwind-friendly single-page experience that runs
multiple Gemma agents concurrently using Ollama.

Key goals:
- Full live partial text streaming per agent
- Tailwind cards (matching the spirit of the original Google demo)
- Defaults tuned for 16 GB VRAM (4 agents @ 16k context)
- Dark modern aesthetic with subtle NVIDIA-inspired accents
"""

import time
import json
import threading
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import gradio as gr

from scenarios import (
    get_scenario,
    live_agent_card,
    build_page,
)
import ollama
from llm_client import OllamaClient, build_messages, chat_once, GenerationMetrics

def get_available_models():
    try:
        models = ollama.list().get("models", [])
        names = [m.get("name") or m.get("model", "") for m in models]
        return [n for n in names if n] or ["gemma2:27b", "gemma2:9b"]
    except Exception:
        return ["gemma2:27b", "gemma2:9b", "qwen2.5:14b"]

# Dynamic suggestions per scenario
SCENARIO_SUGGESTIONS = {
    "fractals": "A friendly robot exploring a neon garden",
    "translate": "The quick brown fox jumps over the lazy dog",
    "code": "Implement a simple rate limiter",
    "ascii": "A tiny spaceship landing on the moon",
    "explanations": "How does the internet actually work?",
}

def update_suggestion(scenario_name):
    return SCENARIO_SUGGESTIONS.get(scenario_name, "Describe the topic")


# ──────────────────────────────────────────────────────────────────────────────
# Styling — Dark + NVIDIA/Windows tech feel
# ──────────────────────────────────────────────────────────────────────────────

CUSTOM_CSS = """
:root {
    --matrix-green: #00ff41;
}

.gradio-container, .gradio-container * {
    background: #000000 !important;
    color: #00ff41 !important;
    font-family: 'Courier New', monospace !important;
    font-size: 12px;
}

h1, h2, .gr-markdown h1, .gr-markdown h2, label {
    color: #ffffff !important;
}

.dark .gr-button-primary {
    background: #000000 !important;
    border: 2px solid #00ff41 !important;
    color: #ffffff !important;
    font-weight: 700;
}

.gr-button-primary:hover {
    background: #00ff41 !important;
    color: #000000 !important;
    border-color: #ffffff !important;
}

.agent-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 4px;
}

.stats-bar {
    background: #000000;
    border: 1px solid #00ff41;
}

.log-box textarea {
    background: #000000 !important;
    color: #00ff41 !important;
    border: 1px solid #00ff41;
    font-size: 10px;
}

/* Force single pane, minimal scroll */
.gradio-container { 
    padding: 2px 6px !important; 
    max-height: 98vh;
    overflow-y: auto;
}
.gr-row, .gr-column, .gr-form, .gr-box, .gr-accordion { 
    gap: 2px !important; 
    margin: 0 !important; 
    padding: 1px !important; 
}
.gr-textbox textarea, .gr-dropdown, .gr-slider { 
    margin: 0 !important; 
    min-height: 24px !important;
}

/* Ensure labels are visible in Matrix theme */
label, .gr-label, .gr-form-label {
    color: #ffffff !important;
    font-size: 10px !important;
    font-weight: 600 !important;
    display: block !important;
    margin-bottom: 1px !important;
}

/* Keep top controls area from taking too much space (target ~1/3) */
.gradio-container .gr-row:first-of-type,
.gradio-container .gr-row:nth-of-type(2) {
    max-height: 18vh;
}
"""

# (theme removed for full custom CSS control)


# ──────────────────────────────────────────────────────────────────────────────
# Shared state for live updates
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RunState:
    agents: list[dict] = field(default_factory=list)
    agent_data: dict[str, dict] = field(default_factory=dict)  # name -> live info
    log_lines: list[str] = field(default_factory=list)
    overall_tps: float = 0.0
    total_tokens: int = 0
    elapsed: float = 0.0
    status: str = "idle"
    final_gallery_html: str = ""
    planning_text: str = ""


def append_log(state: RunState, line: str):
    state.log_lines.append(line)
    if len(state.log_lines) > 60:
        state.log_lines = state.log_lines[-60:]


def build_live_grid_html(state: RunState) -> str:
    """Builds a Tailwind-powered live grid of all agents."""
    if not state.agents:
        return '<div class="text-center text-slate-500 py-8">Agents will appear here when you run...</div>'

    cards = []
    for agent in state.agents:
        name = agent["name"]
        info = state.agent_data.get(name, {})
        status = info.get("status", "waiting")
        partial = info.get("partial", "")
        tps = info.get("tps", 0.0)
        tokens = info.get("tokens", 0)

        card_html = live_agent_card(agent, status, partial, tps, tokens)
        cards.append(f'<div class="min-h-[210px]">{card_html}</div>')

    grid = f"""
<div class="agent-grid">
{chr(10).join(cards)}
</div>
"""
    return grid


def build_stats_html(state: RunState) -> str:
    status_color = "#00ff41"
    if state.status == "planning":
        status_color = "#ffff00"
    elif state.status == "error":
        status_color = "#ff0000"
    elif state.status == "done":
        status_color = "#ffffff"

    running = sum(1 for d in state.agent_data.values() if d.get("status") == "running")
    done = sum(1 for d in state.agent_data.values() if d.get("status") == "done")

    return f"""
<div style="background:#000; border:1px solid #00ff41; padding:3px 6px; font-family:monospace; font-size:9px; color:#00ff41; display:flex; gap:8px; align-items:center;">
  <div><span style="color:#fff;">ST</span> <span style="color:{status_color};">{state.status[:4].upper()}</span></div>
  <div><span style="color:#fff;">A</span> {running}/{done}</div>
  <div><span style="color:#fff;">TPS</span> <span style="color:#00ff41;">{state.overall_tps:.1f}</span></div>
  <div><span style="color:#fff;">T</span>{state.total_tokens}</div>
  <div><span style="color:#fff;">{state.elapsed:.0f}s</span></div>
</div>
"""


# ──────────────────────────────────────────────────────────────────────────────
# Core orchestration (in-memory, concurrent, streaming)
# ──────────────────────────────────────────────────────────────────────────────

def run_single_specialist(
    client: OllamaClient,
    model: str,
    agent: dict,
    system_prompt: str,
    ollama_options: dict,
    state: RunState,
    lock: threading.Lock,
):
    """Worker that runs one agent with full streaming updates."""
    name = agent["name"]
    instruction = agent.get("direct_instruction", f"Work on: {name}")

    # Replace {topic} if the instruction contains the placeholder
    # (some scenarios embed it)
    # The actual instruction comes from the planning step in a real run.

    def on_chunk(text_chunk: str):
        with lock:
            data = state.agent_data.setdefault(name, {})
            is_first = not data.get("partial")
            data["partial"] = data.get("partial", "") + text_chunk
            data["status"] = "running"
            if is_first:
                import time as _t
                append_log(state, f"[{name}] FIRST TOKEN at {_t.strftime('%H:%M:%S')}")

    def on_metrics(m: GenerationMetrics):
        with lock:
            data = state.agent_data.setdefault(name, {})
            data["status"] = m.status
            data["tps"] = m.tps
            data["tokens"] = m.tokens
            data["partial"] = m.text or data.get("partial", "")

            # Update global stats
            total_tps = 0.0
            total_tok = 0
            for d in state.agent_data.values():
                total_tps += d.get("tps", 0)
                total_tok += d.get("tokens", 0)
            state.overall_tps = round(total_tps, 1)
            state.total_tokens = total_tok

    messages = build_messages(system_prompt, instruction)

    import time as _time
    start_ts = _time.strftime("%H:%M:%S")
    with lock:
        append_log(state, f"[{name}] STARTING LLM call at {start_ts} (submitting to Ollama)...")

    full, metrics = client.stream_chat(
        model=model,
        messages=messages,
        ollama_options=ollama_options,
        on_chunk=on_chunk,
        on_metrics=on_metrics,
    )

    with lock:
        state.agent_data[name]["status"] = metrics.status
        state.agent_data[name]["partial"] = full
        state.agent_data[name]["tps"] = metrics.tps
        state.agent_data[name]["tokens"] = metrics.tokens
        append_log(state, f"[{name}] done — {metrics.tokens} tokens @ {metrics.tps:.1f} t/s")

    return full


def execute_concurrent(
    scenario_name: str,
    topic: str,
    n_agents: int,
    model: str,
    ollama_options: dict,
    host: str = "http://localhost:11434",
):
    """
    Generator that drives the entire multi-agent run and yields UI updates.
    This gives us smooth live partial text.
    """
    state = RunState()
    lock = threading.Lock()

    client = OllamaClient(host=host)

    # 1. Load scenario
    scenario = get_scenario(scenario_name, n_agents)
    agents = scenario["agents"]
    state.agents = agents

    system_prompt = scenario.get("system_prompt", "")
    plan_spec = scenario["plan"]

    with lock:
        state.status = "planning"
        append_log(state, f"Starting scenario: {scenario_name} with {len(agents)} agents")
        append_log(state, f"Model: {model} | num_ctx: {ollama_options.get('num_ctx', '?')}")
        append_log(state, "Note: run.bat / startup only kills Ollama Desktop (CLI serve is respected when already up). Use Apply button to force restart serve for new agent counts.")

    # Yield initial state
    yield (
        build_stats_html(state),
        build_live_grid_html(state),
        "\n".join(state.log_lines),
        "",  # final gallery
    )

    # 2. Planning step (orchestrator)
    agent_list = ", ".join(a["name"] for a in agents)
    user_prompt = plan_spec["user"].replace("{topic}", topic).replace("{agent_list}", agent_list)

    plan_messages = [
        {"role": "system", "content": plan_spec["system"]},
        {"role": "user", "content": user_prompt},
    ]

    with lock:
        append_log(state, "🧠 Orchestrator planning tasks...")

    try:
        raw_plan = chat_once(model, plan_messages, ollama_options=ollama_options, host=host)
    except Exception as e:
        raw_plan = f"[]"
        with lock:
            append_log(state, f"Planning error: {e}")

    # Extract JSON tasks
    import re
    tasks = []
    try:
        start = raw_plan.find("[")
        end = raw_plan.rfind("]")
        if start != -1 and end != -1:
            json_str = raw_plan[start : end + 1]
            tasks = json.loads(json_str)
    except Exception:
        tasks = []

    if not tasks:
        tasks = [{"name": a["name"], "instruction": f"Work on: {topic}"} for a in agents]

    # Attach instructions back to agents
    task_map = {t.get("name"): t.get("instruction", "") for t in tasks}
    for agent in agents:
        agent["direct_instruction"] = task_map.get(agent["name"], agent.get("direct_instruction", f"Process: {topic}"))

    with lock:
        state.planning_text = raw_plan[:300]
        append_log(state, f"✅ Plan received: {len(tasks)} tasks")
        for t in tasks[:6]:
            append_log(state, f"   → {t.get('name')}: {str(t.get('instruction',''))[:60]}")
        state.status = "running"
        append_log(state, "🚀 All agents submitted concurrently.")
        append_log(state, "   >>> Check Execution Log for 'STARTING LLM call at HH:MM:SS' and 'FIRST TOKEN at HH:MM:SS' times per agent.")

    yield (
        build_stats_html(state),
        build_live_grid_html(state),
        "\n".join(state.log_lines),
        "",
    )

    # 3. Dispatch + concurrent execution
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max(2, len(agents))) as executor:
        future_to_name = {}
        for agent in agents:
            with lock:
                state.agent_data[agent["name"]] = {
                    "status": "waiting",
                    "partial": "",
                    "tps": 0.0,
                    "tokens": 0,
                }

            fut = executor.submit(
                run_single_specialist,
                client, model, agent, system_prompt, ollama_options, state, lock
            )
            future_to_name[fut] = agent["name"]

        with lock:
            append_log(state, "Workers queued. Parallel start depends on Ollama (see top yellow warning).")

        # Live polling loop — this gives the streaming effect
        while any(fut.running() or not fut.done() for fut in future_to_name):
            with lock:
                state.elapsed = time.time() - start_time
                # Recompute aggregate tps
                total_tps = sum(d.get("tps", 0) for d in state.agent_data.values())
                state.overall_tps = round(total_tps, 1)

            yield (
                build_stats_html(state),
                build_live_grid_html(state),
                "\n".join(state.log_lines),
                "",
            )
            time.sleep(0.18)

        # Collect final results
        results = {}
        for fut in as_completed(future_to_name):
            name = future_to_name[fut]
            try:
                results[name] = fut.result()
            except Exception as e:
                results[name] = f"[ERROR] {e}"

    # 4. Assemble final gallery
    with lock:
        state.status = "done"
        state.elapsed = time.time() - start_time
        append_log(state, "🎉 All agents complete. Building gallery...")

    final_html = build_page(topic, scenario, results, tasks=tasks)

    with lock:
        state.final_gallery_html = final_html
        append_log(state, "✅ Gallery ready")

    yield (
        build_stats_html(state),
        build_live_grid_html(state),
        "\n".join(state.log_lines),
        final_html,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Gradio UI
# ──────────────────────────────────────────────────────────────────────────────

def create_app():
    # Only kill the Desktop app on startup. We deliberately leave any CLI "ollama serve"
    # (started in separate CMD, or by run.bat when it detected none) running.
    # The "Apply OLLAMA_NUM_PARALLEL" button does a full kill+restart when you explicitly want to change counts.
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'Ollama Desktop.exe', '/T'], capture_output=True, shell=True)
    except Exception:
        pass

    with gr.Blocks(
        title="Concurrent Gemma — Local RTX",
    ) as demo:
        gr.HTML("""
<div style="text-align:center; padding:1px 0; border-bottom:1px solid #00ff41; margin-bottom:2px; line-height:1;">
    <span style="font-size:16px; color:#00ff41;">CONCURRENT GEMMA</span>
    <span style="font-size:8px; color:#fff; margin-left:6px;">MATRIX | BLACK BG + GREEN TEXT</span>
</div>
""")

        ollama_status = gr.HTML(value="Checking Ollama...")

        # === TOP CONTROLS (kept to ~top 1/3) ===
        # Single row: [Scenario | Ollama Model]   [Topic / Prompt ................] [RUN]
        with gr.Row():
            scenario = gr.Dropdown(
                choices=["code", "explanations", "translate", "ascii", "fractals"],
                value="code",
                label="Scenario",
                scale=1
            )
            model_choices = get_available_models()
            default_model = "gemma2:27b" if "gemma2:27b" in model_choices else (model_choices[0] if model_choices else "gemma2:9b")
            model = gr.Dropdown(
                choices=model_choices,
                value=default_model,
                label="Ollama Model",
                allow_custom_value=True,
                scale=2
            )
            refresh_models = gr.Button("↻", size="sm", scale=0, min_width=30)

            topic = gr.Textbox(
                value=SCENARIO_SUGGESTIONS.get("code", "Implement a rate limiter"),
                label="Topic / Prompt",
                lines=1,
                scale=4
            )

            run_btn = gr.Button("▶ RUN CONCURRENT AGENTS", variant="primary", size="lg", scale=2)
            power_btn = gr.Button("⏻ Kill & Unload", variant="stop", size="sm", scale=0, min_width=80)

        gr.HTML("""
<div style="font-size:9px; color:#ffcc00; margin-top:2px; border:1px solid #ffcc00; padding:4px;">
<b>Port busy?</b> Use the "🧹 Free port 11434" button below, then start <code>ollama serve</code> in a separate terminal with <code>$env:OLLAMA_NUM_PARALLEL=4</code>.<br>
run.bat now detects a live serve and skips its own start (no more hanging). Apply button does full reconfig.
</div>
""")

        # Compact config row (keeps top ~1/3)
        with gr.Row():
            n_agents = gr.Slider(
                minimum=1, maximum=8, value=3, step=1,
                label="Concurrent Agents", scale=1
            )
            context = gr.Slider(
                minimum=4096, maximum=32768, value=8192, step=4096,
                label="Context (num_ctx)", scale=2
            )
            temperature = gr.Slider(0.0, 1.5, value=0.7, step=0.05, label="Temp", scale=1)
            top_p = gr.Slider(0.1, 1.0, value=0.9, step=0.05, label="Top P", scale=1)

        # Parallelism control
        with gr.Row():
            apply_parallel = gr.Button("🔄 Apply OLLAMA_NUM_PARALLEL (kill + restart serve)", size="sm", scale=2)
            free_port_btn = gr.Button("🧹 Free port 11434 (kill whatever is listening)", size="sm", scale=1)
            parallel_status = gr.Textbox(value="", label="", scale=3, interactive=False, container=False)

        # === BOTTOM QUADRANTS: Live left, Gallery right ===
        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML("<div style='color:#ffffff; font-size:10px; margin-bottom:2px; border-bottom:1px solid #00ff41; font-weight:bold;'>LIVE FEED (bottom-left quadrant)</div>")
                stats_html = gr.HTML(value=build_stats_html(RunState()))
                live_grid = gr.HTML(
                    value='<div style="padding:4px; background:#000000; border:1px solid #00ff41; color:#00ff41; font-family:monospace; font-size:9px; min-height:90px; max-height:180px; overflow:auto;">Click RUN to start streaming agents.</div>'
                )

            with gr.Column(scale=1):
                gr.HTML("<div style='color:#ffffff; font-size:10px; margin-bottom:2px; border-bottom:1px solid #00ff41; font-weight:bold;'>FINAL OUTPUT (bottom-right quadrant)</div>")
                final_html = gr.HTML(value="")
                highlight_btn = gr.Button("Re-highlight code (if needed)", size="sm", variant="secondary")

        # === BOTTOM RIBBON: Expandable log + settings ===
        with gr.Accordion("▼ RIBBON: Execution Log | Gradio Info (expandable)", open=False):
            with gr.Row():
                with gr.Column():
                    log_output = gr.Textbox(
                        value="",
                        lines=6,
                        max_lines=8,
                        label="Execution Log",
                        elem_classes="log-box"
                    )
                with gr.Column():
                    gr.HTML("<div style='font-size:9px; color:#888;'>Use the Apply button above to manage OLLAMA_NUM_PARALLEL automatically.</div>")

        # === Wiring ===
        def refresh_model_list():
            new_models = get_available_models()
            # Prefer gemma2:27b if available
            preferred = "gemma2:27b" if "gemma2:27b" in new_models else (model.value if model.value in new_models else (new_models[0] if new_models else "gemma2:9b"))
            return gr.update(choices=new_models, value=preferred)

        refresh_models.click(refresh_model_list, outputs=[model])

        def apply_ollama_parallel(n):
            n = max(1, int(n))
            try:
                # Explicit reconfig: aggressively free port 11434 (PID-based + name-based)
                # 1. Kill listeners on the exact port (most reliable)
                try:
                    subprocess.run(
                        ['powershell', '-Command',
                         "Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue | "
                         "Where-Object { $_.State -eq 'Listen' } | "
                         "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
                        capture_output=True, shell=True, timeout=5
                    )
                except Exception:
                    pass

                # 2. Kill by known names too
                for name in ['ollama.exe', 'Ollama Desktop.exe']:
                    subprocess.run(['taskkill', '/F', '/IM', name, '/T'], capture_output=True, shell=True)

                time.sleep(1.2)

                env = os.environ.copy()
                env['OLLAMA_NUM_PARALLEL'] = str(n)

                # Launch new serve in minimized window with env
                subprocess.Popen(
                    ['cmd', '/c', f'set OLLAMA_NUM_PARALLEL={n} && start /min ollama serve'],
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, 'DETACHED_PROCESS', 0)
                )
                time.sleep(2)
                return f"✅ Restarted ollama serve with OLLAMA_NUM_PARALLEL={n}. Wait 3-5s then click RUN. (Port 11434 was force-freed.)"
            except Exception as e:
                return f"❌ Error: {str(e)}"

        apply_parallel.click(apply_ollama_parallel, inputs=[n_agents], outputs=[parallel_status])

        def free_ollama_port():
            try:
                # PID-based kill on 11434
                subprocess.run(
                    ['powershell', '-Command',
                     "Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue | "
                     "Where-Object { $_.State -eq 'Listen' } | "
                     "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
                    capture_output=True, shell=True, timeout=6
                )
                # Name fallback
                for name in ['ollama.exe', 'Ollama Desktop.exe']:
                    subprocess.run(['taskkill', '/F', '/IM', name, '/T'], capture_output=True, shell=True)
                time.sleep(0.8)
                return "✅ Port 11434 freed (if anything was holding it). Now start 'ollama serve' in a terminal with $env:OLLAMA_NUM_PARALLEL=4"
            except Exception as e:
                return f"❌ Error freeing port: {e}"

        free_port_btn.click(free_ollama_port, outputs=[parallel_status])

        # Update topic when scenario changes
        scenario.change(
            fn=update_suggestion,
            inputs=[scenario],
            outputs=[topic]
        )

        def update_max_agents(model_name):
            if model_name and ("27b" in str(model_name).lower() or "27" in str(model_name)):
                return gr.update(maximum=3)
            return gr.update(maximum=8)

        model.change(update_max_agents, inputs=[model], outputs=[n_agents])

        def on_run_click(scenario_name, topic_text, n_agents_val, num_ctx_val, model_val, temp_val, top_p_val):
            if not topic_text.strip():
                topic_text = "Generative AI and the future"

            effective_agents = max(1, int(n_agents_val))

            # Build dynamic ollama options from current UI values
            ollama_opts = {
                "num_ctx": int(num_ctx_val),
                "temperature": float(temp_val),
                "top_p": float(top_p_val),
            }

            yield (
                build_stats_html(RunState(status="starting")),
                '<div style="color:#00ff41; font-size:9px;">STARTING...</div>',
                "INIT",
                ""
            )

            try:
                for stats, grid, log_text, gallery in execute_concurrent(
                    scenario_name, topic_text.strip(), effective_agents, model_val.strip() if model_val else "gemma2:27b", ollama_opts
                ):
                    yield stats, grid, log_text, gallery
            except Exception as ex:
                error_state = RunState(status="error")
                append_log(error_state, f"FATAL: {ex}")
                yield (
                    build_stats_html(error_state),
                    f'<div style="color:#ff4444; font-size:9px;">ERR: {ex}</div>',
                    "\n".join(error_state.log_lines),
                    ""
                )

        run_btn.click(
            fn=on_run_click,
            inputs=[scenario, topic, n_agents, context, model, temperature, top_p],
            outputs=[stats_html, live_grid, log_output, final_html],
            show_progress="full",
        )

        highlight_btn.click(
            fn=None,
            js="() => { if (window.hljs) { window.hljs.highlightAll(); } else { alert('highlight.js not loaded'); } }",
            inputs=[],
            outputs=[]
        )

        def unload_and_kill(model_name):
            if model_name:
                try:
                    ollama.generate(
                        model=model_name,
                        prompt="",
                        options={"keep_alive": 0}
                    )
                except Exception:
                    pass  # ignore unload errors on shutdown

            # Clear UI
            cleared = '<div style="padding:4px; background:#000; border:1px solid #ff4444; color:#ff4444; font-family:monospace; font-size:9px;">POWER OFF - Model unloaded. Killing Python process (this closes the terminal). Close tab manually if needed.</div>'
            # Schedule hard kill of the Python process (kills the batch/terminal that launched it)
            import os, threading, time
            def shutdown():
                time.sleep(1.2)  # let the UI update and tab close attempt
                os._exit(0)
            threading.Thread(target=shutdown, daemon=True).start()

            return (
                gr.update(value=cleared),
                gr.update(value=""),
                build_stats_html(RunState()),
                gr.update(value="POWERED OFF")
            )

        power_btn.click(
            fn=unload_and_kill,
            inputs=[model],
            outputs=[live_grid, final_html, stats_html, log_output],
            js="""
() => {
  // Try hard to close the tab
  try { window.close(); } catch(e) {}
  setTimeout(() => { try { window.close(); } catch(e){} }, 200);
  setTimeout(() => { try { window.close(); } catch(e){} }, 600);
  // As a last resort, navigate away (may leave blank tab)
  setTimeout(() => { try { window.location.href = 'about:blank'; } catch(e){} }, 900);
}
"""
        )

        def check_ollama_status():
            try:
                resp = ollama.list()
                n = len(resp.get("models", []))
                return f'<div style="color:#00ff41; font-size:10px;">✅ Ollama connected ({n} models). If agents serialize, use Apply button (or start your serve with OLLAMA_NUM_PARALLEL set).</div>'
            except Exception as e:
                msg = str(e)
                extra = ""
                if "10061" in msg or "Connect" in msg or "WinError" in msg:
                    extra = "<br><b>Port free?</b> In PS/CMD: <code>netstat -ano | findstr :11434</code> then <code>taskkill /F /PID &lt;PID&gt; /T</code>"
                return f'<div style="color:#ff4444; font-size:10px;">❌ No connection to Ollama (http://localhost:11434)<br>{e}{extra}<br>Start "ollama serve" (with OLLAMA_NUM_PARALLEL) in a separate window, or click Apply below. run.bat now skips if it detects a live serve.</div>'

        demo.load(check_ollama_status, outputs=[ollama_status])

    return demo


if __name__ == "__main__":
    app = create_app()
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
        css=CUSTOM_CSS,
        head="""
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script>
tailwind.config = {
  theme: {
    extend: {
      fontFamily: {
        'mono': ['Courier New', 'monospace']
      }
    }
  }
};
</script>
""",
    )
