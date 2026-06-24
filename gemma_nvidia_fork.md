You are an expert coding agent helping me build a local Windows version of the "Concurrent Gemma" multi-agent demo from the Google Gemma Cookbook.

**Project Goal:**
Create a clean, local-first Windows application that runs multiple concurrent Gemma 4 agents in parallel with a nice visual dashboard. This should feel like an upgraded, cross-platform version of https://github.com/google-gemma/cookbook/tree/main/apps/concurrent, but optimized for my RTX 5080 (16GB VRAM) and easy to extend.

**Key Requirements:**

- **Backend Flexibility**: Support both **Ollama** (preferred for simplicity on Windows) and raw `llama-server` from llama.cpp. Default to Ollama since I already have it installed.
- **Model**: Use a lighter Gemma 4 26B A4B quant suitable for 16GB VRAM (something like `gemma-4-26b-a4b-it` in IQ4_XS or similar). Use sensible defaults: 4–5 concurrent agents, 16k–24k context.
- **UI**: Build a clean **Gradio** web dashboard (localhost) showing:
  - Controls for scenario, topic, number of agents, and context length
  - Live view of multiple agents working in parallel (status, outputs, progress)
  - Real-time logs or streaming where possible
- **Core Features**:
  - Multi-agent orchestration (similar to the original demo)
  - Pre-built scenarios (SVG generation, code generation, translation, ASCII art) + easy way to add custom ones
  - Good defaults tuned for my hardware so it "just works" without OOM
  - Clean project structure that's easy to maintain
- **Tech Stack**:
  - Python + Gradio for the UI
  - Ollama (via `ollama` Python library) as the primary backend
  - Optional support for llama.cpp server later
  - Modern, readable code with good comments

**Constraints**:
- Must run comfortably on Windows 11 + RTX 5080 16GB
- Keep it lightweight and local-only (no cloud dependencies)
- Make the UI look professional and useful beyond just a demo

**Deliverables**:
1. Full project folder structure
2. `requirements.txt`
3. Main Gradio app (`app.py`)
4. Agent orchestration logic
5. Example scenarios
6. A `README.md` with setup instructions and recommended Ollama model + settings
7. A simple way to launch everything (`run.bat` or instructions)

Start by proposing the project structure, then generate the key files. Ask clarifying questions if needed before writing large amounts of code.