from dataclasses import dataclass

from app.db.session import project_root


SUPPORTED_EXTENSIONS = {".txt", ".md", ".doc", ".docx", ".pdf", ".ppt", ".pptx"}
MAX_SOURCE_BYTES = 50 * 1024 * 1024
CHUNK_SIZE = 900
CHUNK_OVERLAP = 100


@dataclass(frozen=True)
class KnowledgeChunk:
    locator: str
    text: str


@dataclass(frozen=True)
class KnowledgeDocument:
    text: str
    chunks: list[KnowledgeChunk]


def split_knowledge_text(text: str, locator: str) -> list[KnowledgeChunk]:
    if not text.strip():
        return []
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise ValueError("Knowledge splitting is unavailable; install backend requirements") from exc
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    return [KnowledgeChunk(locator=locator, text=piece) for piece in splitter.split_text(text) if piece.strip()]


def parse_knowledge_file(relative_path: str) -> KnowledgeDocument:
    root = project_root().resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Knowledge file is unavailable")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported knowledge file type: {path.suffix or 'none'}")
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Knowledge file exceeds 50 MB")
    try:
        import sharepoint2text
    except ImportError as exc:
        raise ValueError("Knowledge parsing is unavailable; install backend requirements") from exc
    try:
        document, = sharepoint2text.read_file(path, ignore_images=True, max_file_size=MAX_SOURCE_BYTES)
        chunks = [chunk for unit in document.units
                  for chunk in split_knowledge_text(
                      unit.text, f"{unit.kind.title()} {unit.number}" if unit.number is not None else unit.kind.title())]
        if not chunks and document.full_text.strip():
            chunks = split_knowledge_text(document.full_text, "Document")
        return KnowledgeDocument(text=document.full_text.strip(), chunks=chunks)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Unable to parse {path.suffix.lower()} knowledge file: {exc}") from exc
