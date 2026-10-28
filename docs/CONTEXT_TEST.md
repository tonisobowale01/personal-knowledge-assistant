# Testing an 8192-token model context

The context window is the space available to instructions, retrieved notes, recent messages, the question, and generated output in one model request. It does not limit the chats saved in SQLite.

Run from the repository root while avoiding other requests to Ollama:

```powershell
.\.venv\Scripts\python.exe benchmark_context.py
```

This reads the existing Chroma collection and freezes three note-based prompts (a direct question, a comparison, and a follow-up). It runs the same prompts at 131072 and 8192 tokens with temperature 0, seed 42, and the same 256-token output limit. A warm-up is measured separately for each context. By default it repeats each question twice. It writes context_report.json after each completed request, so progress is retained if a later request fails. Model calls have a 180-second timeout.

The initial quick comparison uses --repeats 1. For stronger evidence, repeat the test and reverse the context order:

```powershell
.\.venv\Scripts\python.exe benchmark_context.py --contexts 8192 131072 --output context_report_reverse.json
```

Inspect wall_seconds, first_text_seconds, load_seconds, prompt_eval_seconds, output_tokens_per_second, and Ollama-reported allocation. Whole-program RAM is not measured. Same prompt hashes and equal prompt-token counts across settings help detect input trimming for these samples; they do not prove every future prompt will fit. Check all_budgets_ok and any_output_hit_limit, then compare the saved answers with the review_points. A cut-off answer is not a successful quality comparison.

Retrieval is done once before timing generation, so this isolates the context-size change. It does not measure end-to-end API latency or test the rewrite quality at both sizes. Benchmark prompts follow the app's instructions but differ in whitespace. The application currently waits for the complete response; first-text latency is a diagnostic, not a frontend streaming improvement.

No application setting, note content, or saved chat is modified. The benchmark temporarily reloads the local model at each context size. The next application request uses its own existing setting.

If testing supports adopting 8192, the application's LlamaIndex Ollama constructor can explicitly receive context_window=8192. That translates to Ollama's num_ctx setting. Before adopting it, also test the longest real prompts and either enforce a token budget or reject oversized inputs visibly; do not silently drop important notes or history. This test alone does not implement that protection.
