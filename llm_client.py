"""
llm_client.py — Ollama streaming client for Concurrent Gemma (RTX / Windows edition).

Designed for:
- Full streaming of partial text (live updates in Gradio)
- Reasonable t/s estimation during generation
- num_ctx support (16k default)
- Clean separation from UI and orchestration

We use the official `ollama` Python library.
For best multi-agent performance on Windows, users should set:
    set OLLAMA_NUM_PARALLEL=4
before starting Ollama.
"""

import time
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

import ollama


@dataclass
class GenerationMetrics:
    name: str
    status: str          # waiting | running | done | error
    tokens: int
    elapsed_s: float
    tps: float
    text: str = ""


def estimate_tokens(text: str) -> int:
    """Rough but fast token estimate. Good enough for live UI."""
    if not text:
        return 0
    # ~4 chars per token is a common English heuristic
    return max(1, len(text) // 4)


class OllamaClient:
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host
        # The ollama library reads OLLAMA_HOST env var automatically in many cases,
        # but we can explicitly set client if needed.
        self._client = ollama.Client(host=host)

    def stream_chat(
        self,
        model: str,
        messages: list[dict],
        ollama_options: dict = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        on_metrics: Optional[Callable[[GenerationMetrics], None]] = None,
    ) -> tuple[str, GenerationMetrics]:
        """
        Stream a chat completion.

        ollama_options: dict passed directly to ollama.chat options (num_ctx, temperature, etc.)
        """
        if ollama_options is None:
            ollama_options = {"num_ctx": 16384}

        start = time.time()
        full_text = ""
        chunk_count = 0
        last_tps_update = start
        tokens_since_update = 0

        metrics = GenerationMetrics(
            name="",
            status="running",
            tokens=0,
            elapsed_s=0.0,
            tps=0.0,
        )

        try:
            if on_metrics:
                on_metrics(metrics)

            stream = self._client.chat(
                model=model,
                messages=messages,
                stream=True,
                options=ollama_options,
            )

            for chunk in stream:
                content = ""
                if "message" in chunk and chunk["message"]:
                    content = chunk["message"].get("content", "") or ""

                if content:
                    full_text += content
                    chunk_count += 1

                    if on_chunk:
                        on_chunk(content)

                    now = time.time()
                    tokens_since_update += 1

                    # Update live metrics every ~250ms
                    if (now - last_tps_update) > 0.25:
                        elapsed = now - start
                        current_tokens = estimate_tokens(full_text)
                        tps = (current_tokens / elapsed) if elapsed > 0.1 else 0.0

                        metrics = GenerationMetrics(
                            name=metrics.name,
                            status="running",
                            tokens=current_tokens,
                            elapsed_s=round(elapsed, 2),
                            tps=round(tps, 1),
                            text=full_text,
                        )
                        if on_metrics:
                            on_metrics(metrics)

                        last_tps_update = now
                        tokens_since_update = 0

                # Final chunk often contains usage info
                if chunk.get("done"):
                    eval_count = chunk.get("eval_count")
                    if eval_count:
                        chunk_count = eval_count

            # Finalize
            total_elapsed = time.time() - start
            final_tokens = estimate_tokens(full_text)
            if chunk_count and chunk_count > final_tokens:
                final_tokens = chunk_count

            final_tps = (final_tokens / total_elapsed) if total_elapsed > 0.1 else 0.0

            final_metrics = GenerationMetrics(
                name=metrics.name,
                status="done",
                tokens=final_tokens,
                elapsed_s=round(total_elapsed, 2),
                tps=round(final_tps, 1),
                text=full_text,
            )

            if on_metrics:
                on_metrics(final_metrics)

            return full_text, final_metrics

        except Exception as e:
            err_metrics = GenerationMetrics(
                name=metrics.name or "unknown",
                status="error",
                tokens=estimate_tokens(full_text),
                elapsed_s=round(time.time() - start, 2),
                tps=0.0,
                text=full_text + f"\n[ERROR: {e}]",
            )
            if on_metrics:
                on_metrics(err_metrics)
            return full_text + f"\n[ERROR: {e}]", err_metrics


def build_messages(system_prompt: str, user_instruction: str) -> list[dict]:
    """Helper to build the messages list for Ollama."""
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.append({"role": "user", "content": user_instruction})
    return msgs


# Convenience function for simple one-off calls (used by orchestrator planning)
def chat_once(
    model: str,
    messages: list[dict],
    ollama_options: dict = None,
    host: str = "http://localhost:11434",
) -> str:
    """Non-streaming helper, useful for the planning step."""
    if ollama_options is None:
        ollama_options = {"num_ctx": 16384}
    client = ollama.Client(host=host)
    response = client.chat(
        model=model,
        messages=messages,
        stream=False,
        options=ollama_options,
    )
    return response["message"]["content"]
