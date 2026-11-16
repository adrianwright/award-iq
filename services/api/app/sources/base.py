def evidence_doc_url(subdir: str, filename: str) -> str:
    """Relative URL to the backend document-serving endpoint, so citation links open the real
    synthetic source content (served from data/<subdir>/<filename>)."""
    return f"/api/evidence/doc?path={subdir}/{filename}"
