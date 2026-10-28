# Streaming and CPU performance

The frontend now calls POST /ask/stream. The API sends newline-delimited JSON status, delta, done, or error events. The browser appends answer text as deltas arrive. Source preview links appear after completion. POST /ask remains available and uses the same answer pipeline.

The model context is explicitly 8192 tokens and the request timeout is 180 seconds. No manual thread setting was adopted. There is no added output cap in the application. The model request still includes the recent four messages and up to five selected note passages. Very long questions or messages can exceed the context window; the earlier three-prompt test does not prove that every future input fits. A full model-token budget check remains future work.

Only complete model responses are committed as a question/answer pair. A model error, missing terminal marker, or length-limited response fails rather than saving a partial exchange. The browser restores saved history after an interrupted or failed stream. A disconnect near completion can leave a completed exchange saved even if the browser missed the acknowledgement; reopening the chat resolves this uncertainty. Disconnecting does not guarantee immediate cancellation of a synchronous model call already in progress.

Status messages identify retrieval and model preparation. Streaming exposes words once generation starts; it cannot remove the earlier rewrite, embedding, or prompt-processing delay. Retrieval, first-text, model-load, prompt-processing, and decode speed are included in completion timings and logged by the backend. The current browser does not display the technical metrics.

## CPU experiment

Hardware inspected: Intel Core i7-10510U, 4 physical cores and 8 logical processors. Ollama version: 0.40.3. The prior 8192-context note-based tests generated approximately 4.6 to 7.0 tokens per second. For the topology prompt, prompt processing took about 63 seconds, followed by about 56 seconds generating the capped test output. For the Round Robin follow-up, prompt processing took about 42 seconds, followed by about 6 seconds of generation. These are model stages, not vector lookup timings.

benchmark_cpu.py compares a short fixed synthetic prompt with context=8192 and a 64-token output cap. Each requested thread setting is warmed, then measured twice. It saves cpu_report.json. The first experiment produced median generation rates of 8.64 tokens/second for automatic threads, 7.00 for four threads, and 7.00 for eight threads. The short repeated prompt benefits from caching; this does not establish end-to-end speed for long documents. Thermal conditions, background processes, test order, and the actual worker count were not controlled. No manual-thread speed improvement was demonstrated.

Run again while avoiding other Ollama requests:

```powershell
.\.venv\Scripts\python.exe benchmark_cpu.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node tests/test_frontend.cjs
```

Tests include a real local HTTP connection where the first delta is received before model completion is released. Frontend checks cover incremental reads, UTF-8 split across chunks, missing completion, model errors, and history recovery. Browser visual behavior has not been verified.

Potential next improvements are a comparison with a smaller local model, better selection of compact supporting passages, and separate tuning of prompt-processing settings. A smaller model may trade answer quality for speed and should be evaluated before adoption. No additional model was downloaded.

## Live installed-pipeline check

A live FCFS request completed successfully and emitted text before completion. Retrieval took 2.02 seconds; first text arrived 27.63 seconds after starting the pipeline. The model stage took 29.22 seconds, including 10.59 seconds of loading and 13.45 seconds processing the prompt; decode throughput was 3.76 tokens/second. This is one live request with model loading, not a fair warm comparison with the short CPU benchmark. It demonstrates why streaming alone cannot remove the first-word delay. The final answer and its os_sample.txt source were received correctly.
