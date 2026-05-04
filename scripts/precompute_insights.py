from app.api.services.data import load_sales_data
from app.api.services.insight_service import run_llm_pipeline
from app.insights.detectors import run_detectors_batch
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_LLM_WORKERS = 1

if __name__ == "__main__":
    import time
    start = time.time()

    # Phase 1 — single batch pass (replaces ProcessPoolExecutor)
    df = load_sales_data()
    batch_metrics = run_detectors_batch(df)   # one call, all partners

    # Phase 2+3 — controlled LLM pipeline per partner
    print(f"\n⏳ Phase 2+3 — LLM generation + eval...")
    with ThreadPoolExecutor(max_workers=MAX_LLM_WORKERS) as executor:
        futures = {
            executor.submit(
                run_llm_pipeline, pid, metrics
            ): pid
            for pid, metrics in batch_metrics.items()
        }
        for future in as_completed(futures):
            pid = futures[future]
            try:
                record = future.result()
                print(f"  ✅ {pid} — confidence: {record['confidence']}, "
                      f"factuality: {record['factuality_score']:.0%}")
            except Exception as e:
                print(f"  ❌ {pid} failed: {e}")

    elapsed = time.time() - start
    print(f"\n✅ All partners processed in {elapsed:.1f}s")