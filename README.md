# Concurrent Gemma — Local RTX Edition

**A Windows-first, Gradio + Ollama adaptation** of the original multi-agent demo from the Google Gemma Cookbook.

> **Fork lineage**: This project is derived from  
> https://github.com/google-gemma/cookbook/tree/main/apps/concurrent  
> Core orchestration, scenarios, planning prompts, and gallery rendering are based on the original work.

Run multiple concurrent Gemma (or compatible) agents locally with Ollama, watch them stream in real time, and get beautiful visual results.

Optimized for **RTX 50-series 16 GB** cards (light & fast defaults: 3–4 agents @ 8k–16k context).

## License

MIT License (see [LICENSE](LICENSE)).

This is a derivative work. The original Google Gemma Cookbook concurrent demo is part of a project licensed under Apache-2.0.

## Features

- **Gradio web dashboard** — single localhost app (no Terminal grid hell on Windows)
- **Full live partial text** — every agent streams its output as it generates
- **Tailwind-powered cards** — consistent modern dark aesthetic (NVIDIA/Windows vibe)
- **Four ready scenarios**:
  - SVG Art Gallery
  - Translation Grid
  - Code Gallery (multi-language)
  - ASCII Art Gallery
- Easy to extend with new scenarios
- Hardware-aware defaults (toggleable)

## Quick Start (Windows)

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running
- Ollama running with a suitable model (you currently have Qwen/Llama models; Gemma recommended for the project name):

```powershell
# You currently have these models (example):
ollama list

# To use a Gemma model (recommended for the spirit of this project):
ollama pull gemma2:9b
# or
ollama pull gemma2:27b   # heavier, test with fewer agents

# The app currently defaults to qwen2.5:14b since that's what was installed.
```

**For best parallelism**, set this before launching Ollama (or in the same terminal):

```powershell
$env:OLLAMA_NUM_PARALLEL = "4"
```

### 2. Run the app

```powershell
# Double-click or:
.\run.bat
```

Or manually:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The app opens at http://127.0.0.1:7860

### 3. Use it

1. Choose a scenario
2. Enter a topic
3. Adjust agents (2–6) and context if desired
4. Click **RUN CONCURRENT AGENTS**
5. Watch live streaming output + metrics
6. Enjoy the final Tailwind gallery

## Controls & Hardware Sizing

| Setting          | Recommended (16 GB) | Range     | Notes |
|------------------|---------------------|-----------|-------|
| Agents           | **4**               | 2–6       | 5–6 may still work with light quants |
| Context          | **16384**           | 8k / 16k / 24k | Higher = more VRAM |
| Model            | `gemma-4-26b-a4b-it` | — | Use a 4-bit or IQ quant when possible |

## Architecture (fork notes)

This is a faithful but adapted port:

- **Planning** — one LLM call decomposes the topic into per-agent instructions (exactly like the original)
- **Concurrent specialists** — run via `ThreadPoolExecutor` + true streaming callbacks
- **Live UI** — frequent generator yields update Tailwind HTML cards in real time
- **Final output** — reuses the original `build_page` Tailwind gallery logic

Communication that used to happen via `.agent_comms/` JSON files is now pure in-memory for the single-process Gradio app.

## Adding a New Scenario

Edit `scenarios.py` following the existing pattern (see the big comment block at the top of the file). The original cookbook has great guidance.

## Future / Optional

- llama.cpp server backend (OpenAI-compatible)
- More advanced concurrency (multiple Ollama instances, etc.)
- Export results, video recording of the run, etc.

## Troubleshooting

### "bind: Only one usage of each socket address" (port 11434 already in use)

This happens when something (previous `ollama serve`, Ollama Desktop, or a run from `run.bat`) is still listening on port 11434.

**From PowerShell (or CMD):**

```powershell
# 1. Find what's using the port
netstat -ano | findstr :11434

# PowerShell version (shows process name + PID)
Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalPort, OwningProcess, @{n='Name';e={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName}}

# 2. Kill it (replace 12345 with the actual PID, or kill by name)
taskkill /F /PID 12345 /T
taskkill /F /IM ollama.exe /T
taskkill /F /IM "Ollama Desktop.exe" /T

# 3. Then start your own with the desired parallelism
$env:OLLAMA_NUM_PARALLEL = "4"
ollama serve
```

**In the app:**

- The red status banner on load now suggests the netstat commands.
- Use the **"Apply OLLAMA_NUM_PARALLEL ..."** button — it also does PID-based port freeing before restarting the serve.
- `run.bat` now attempts to detect and kill the port owner before it starts its own minimized serve.

After freeing the port, `run.bat` will detect your manual `ollama serve` and skip its own start (no more pending wait).

### Agents serialize (only 1 running at a time)

Make sure `OLLAMA_NUM_PARALLEL` was set **before** the `ollama serve` process started.
Use the Apply button or restart the serve after setting the variable.

## Credits & Lineage

- Original multi-agent demo, scenarios, prompts, and rendering approach:  
  [google-gemma/cookbook/tree/main/apps/concurrent](https://github.com/google-gemma/cookbook/tree/main/apps/concurrent)
- This repo: Gradio dashboard, Ollama backend, live streaming, Windows packaging, and dark theme adaptations.

## License

MIT License — see the [LICENSE](LICENSE) file for details.

---

Enjoy building with multiple minds at once.
