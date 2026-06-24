"""
test_e2e.py — End-to-end test for Concurrent Gemma using real Ollama.
Tests the full flow: planning + concurrent streaming agents + live updates.
"""

import os
import time

# Set parallelism for better concurrent performance
os.environ.setdefault("OLLAMA_NUM_PARALLEL", "4")

from app import execute_concurrent

def main():
    print("=== End-to-End Test with qwen2.5:14b ===")
    print(f"OLLAMA_NUM_PARALLEL={os.environ.get('OLLAMA_NUM_PARALLEL')}")
    print()

    scenario = "svg"
    topic = "A small friendly robot exploring a sunny garden"
    n_agents = 3
    ctx = 8192
    model = "gemma2:27b"

    print(f"Scenario : {scenario}")
    print(f"Topic    : {topic}")
    print(f"Agents   : {n_agents}")
    print(f"Context  : {ctx}")
    print(f"Model    : {model}")
    print()
    print("Starting execution... (this will take a while as it calls the real LLM)")
    print("-" * 60)

    start = time.time()
    update_count = 0
    last_status = ""
    final_gallery = ""
    final_log = ""

    ollama_opts = {"num_ctx": ctx, "temperature": 0.7}
    try:
        for stats_html, grid_html, log_text, gallery_html in execute_concurrent(
            scenario, topic, n_agents, model, ollama_opts
        ):
            update_count += 1

            # Extract rough status from log
            if log_text:
                lines = log_text.strip().split("\n")
                if lines:
                    last_line = lines[-1][:80]
                    if last_line != last_status:
                        last_status = last_line
                        elapsed = time.time() - start
                        print(f"[{elapsed:6.1f}s] Update #{update_count}: {last_line}")

            if gallery_html:
                final_gallery = gallery_html
                final_log = log_text
                break

            # Safety: don't run forever
            if time.time() - start > 600:
                print("TIMEOUT safety stop after 10 minutes")
                break

    except Exception as e:
        print(f"ERROR during execution: {e}")
        import traceback
        traceback.print_exc()
        return

    total_time = time.time() - start
    print("-" * 60)
    print("=== TEST COMPLETE ===")
    print(f"Total wall time   : {total_time:.1f}s")
    print(f"Total UI updates  : {update_count}")
    print(f"Final gallery size: {len(final_gallery)} characters")
    print()
    print("Last 8 log lines:")
    for line in final_log.strip().split("\n")[-8:]:
        print("   " + line[:110])

    if final_gallery:
        print("\n✅ SUCCESS: Full end-to-end run completed with live streaming updates!")
    else:
        print("\n⚠️  Completed but no final gallery was produced.")

if __name__ == "__main__":
    main()
