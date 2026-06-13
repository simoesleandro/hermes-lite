"""Extração de texto de PDF — compartilhado entre web e Telegram."""


def extract_pdf_text(file_bytes: bytes, filename: str = "document.pdf") -> dict:
    """Retorna {text, filename, pages, truncated, error?}."""
    import fitz

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    n_pages = len(doc)

    if n_pages > 100:
        return {
            "error": f"Documento muito longo ({n_pages} páginas). Máx. 100.",
            "filename": filename,
            "pages": n_pages,
        }

    truncated = False
    if n_pages > 20:
        pages_to_extract = list(range(20)) + list(range(max(20, n_pages - 5), n_pages))
        truncated = True
    else:
        pages_to_extract = list(range(n_pages))

    text = "\n\n".join(doc[i].get_text() for i in pages_to_extract)
    return {
        "text": text,
        "filename": filename,
        "pages": n_pages,
        "truncated": truncated,
    }
