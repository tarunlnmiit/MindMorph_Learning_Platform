# knowledge_base/

Curated corpus for RAG grounding (P1 #7). Drop `.md` or `.txt` files here; each is chunked (~1000
chars, split on blank lines) and embedded into the in-memory vector store when RAG is enabled. The
file's relative path becomes the citation `Source:` shown to the synthesizer.

Enable RAG with `MINDMORPH_RAG=1` (point elsewhere with `MINDMORPH_KNOWLEDGE_DIR`). The first run
downloads the FastEmbed model (`BAAI/bge-small-en-v1.5`, ~once). This `README.md` is ignored by the
loader. Later (P2 #9) user PDF uploads feed the same store.
