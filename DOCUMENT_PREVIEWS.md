# Document previews

Preview links beside Knowledge Base documents and answer sources open PDF/text files in a separate browser tab. PDF source links include #page=N; page navigation depends on browser PDF support. The links do not download files until clicked. Close the preview tab to release its browser resources.

The backend serves the original file with FileResponse, which supports chunked file reads and HTTP byte ranges. No PDF parser, thumbnail generator, embedding call, model call, or document cache is added to the preview route. Browser PDF decoding still consumes memory while open; this feature is not zero-cost. Only PDF and plain text are served inline, with nosniff headers. Paths are restricted to direct files within the repository data/notes folder. Missing originals return 404, including stale vector-index entries.

Upload, deletion, and preview now share the same repository-anchored notes directory. This avoids broken previews when the backend is started from another folder. Upload refreshes the document list. Answer source links are available for new answers; saved chats do not store source metadata, so reopening a chat does not reconstruct clickable sources.

Tests cover encoded filenames, inline content types, byte ranges, missing files, unsupported formats, path escape attempts, lazy frontend links, and PDF page fragments. PDF rendering and page navigation have not been visually verified in a browser.

## Response speed

Retrieval and answer-generation durations are logged separately through the Uvicorn application logger. Retrieval time includes any question rewrite and embedding calls. No model configuration was changed for this feature.

During inspection Ollama reported llama3.2:3b loaded with context_length=131072, size=17883358820 bytes (about 18 GB), and size_vram=0. This is model allocation reported by Ollama, not a full process-memory measurement. It suggests that CPU generation and context memory are worth investigating. A controlled test with a smaller context (for example 8192 tokens), while ensuring the full prompt fits, is the recommended next performance step. Streaming can also reduce the wait before users see the first words, but does not inherently make total generation faster.
