from __future__ import annotations

import json
import hashlib
import logging
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, unquote, urlparse

from app.config import Settings
from app.schemas import Evidence, Source
from app.sources.fabric_funding import FundingDataUnavailable
from app.workiq import WorkIQClient, WorkIQError

logger = logging.getLogger(__name__)


def _document_url_key(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    if parsed.netloc.casefold() != parsed.hostname.casefold():
        return None
    if any(key != "web" or value != "1" for key, value in parse_qsl(parsed.query, keep_blank_values=True)):
        return None

    def decode_unreserved(match: re.Match[str]) -> str:
        char = chr(int(match.group()[1:], 16))
        return char if char.isascii() and (char.isalnum() or char in "-._~ ") else match.group().upper()

    # Do not decode reserved separators, double-encoded paths or opaque source IDs.
    path = re.sub(r"%[0-9a-fA-F]{2}", decode_unreserved, parsed.path)
    return parsed.hostname.casefold(), path


@dataclass(frozen=True)
class FundingWork:
    answer: str
    citations: list[Evidence]
    query: str
    duration_ms: int


def retrieve_funding_work(
    settings: Settings,
    *,
    user_access_token: str | None,
    question: str,
    notice_id: str,
    documents: dict[str, dict[str, str]],
) -> FundingWork:
    """Retrieve grounding from explicitly configured, current demo documents only."""
    if not user_access_token:
        raise FundingDataUnavailable("Work IQ requires the signed-in user's delegated token.")
    if not re.fullmatch(r"FO-\d{4}-\d+", notice_id):
        raise FundingDataUnavailable("Work IQ received an invalid funding notice ID.")
    try:
        configured = json.loads(settings.WORK_IQ_FUNDING_DOCUMENT_URLS)
    except (TypeError, ValueError) as exc:
        raise FundingDataUnavailable("Work IQ funding document URLs are not valid JSON.") from exc
    if not isinstance(configured, dict) or not configured:
        raise FundingDataUnavailable("Work IQ funding document URLs are not configured.")
    try:
        identities = json.loads(settings.WORK_IQ_FUNDING_DOCUMENT_IDENTITIES or "{}")
    except (TypeError, ValueError) as exc:
        raise FundingDataUnavailable("Work IQ funding document identities are not valid JSON.") from exc
    if not isinstance(identities, dict):
        raise FundingDataUnavailable("Work IQ funding document identities are invalid.")
    identity_index: dict[tuple[str, str], str] = {}
    for document_id, identity in identities.items():
        if (
            not isinstance(identity, dict)
            or document_id not in configured
            or identity.get("webUrl") != configured.get(document_id)
            or not isinstance(identity.get("driveId"), str) or not identity["driveId"]
            or not isinstance(identity.get("itemId"), str) or not identity["itemId"]
        ):
            raise FundingDataUnavailable("Work IQ document identities do not match the verified URL map.")
        pair = identity["driveId"], identity["itemId"]
        if pair in identity_index:
            raise FundingDataUnavailable("Work IQ document identities contain a duplicate drive item.")
        identity_index[pair] = document_id

    allowed: dict[str, tuple[str, dict[str, str]]] = {}
    for document_id, url in configured.items():
        if not isinstance(document_id, str) or not isinstance(url, str):
            raise FundingDataUnavailable("Work IQ funding document configuration is invalid.")
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
            or parsed.query
            or url in allowed
        ):
            raise FundingDataUnavailable("Work IQ funding document configuration contains an invalid URL.")
        document = documents.get(document_id)
        if document is not None:
            if document["notice_id"] != notice_id or document["source"] != Source.WORK.value:
                raise FundingDataUnavailable("Work IQ funding document configuration is out of scope.")
            allowed[url] = (document_id, document)
    if not allowed:
        raise FundingDataUnavailable(f"No current Work IQ demo documents are configured for {notice_id}.")

    query = (
        f"Find documented funding decisions, open coordination tasks, owners, deadlines, "
        f"proposed reviews and scheduling constraints for synthetic Award IQ notice {notice_id}. "
        f"Relevant document titles: {json.dumps([item[1]['title'] for item in allowed.values()])}. "
        f"Funding-readiness question: {json.dumps(question)}."
    )
    try:
        answer = WorkIQClient(settings).retrieve(
            user_assertion=user_access_token, query=query, document_urls=list(allowed),
        )
    except WorkIQError as exc:
        raise FundingDataUnavailable(
            f"Work IQ retrieval is unavailable: {exc} Check delegated consent, the user's access "
            "and the demo documents. No packaged Work IQ fallback was used."
        ) from exc
    if not answer.documents:
        raise FundingDataUnavailable(
            "Work IQ retrieved no indexed demo documents from the configured location; "
            "no fallback was used."
        )

    citations: dict[str, Evidence] = {}
    reference_ids: dict[str, str] = {}
    for result in answer.documents:
        returned = urlparse(result.url or "")
        url_key = _document_url_key(result.url) if isinstance(result.url, str) else None
        url_matches = [
            item for url, item in allowed.items()
            if url_key is not None and url_key == _document_url_key(url)
        ]
        identity_document = identity_index.get((result.drive_id or "", result.item_id or ""))
        identity_matches = [
            item for item in allowed.values()
            if item[0] == identity_document
            and returned.scheme == "https"
            and not returned.username and not returned.password
            and returned.hostname == urlparse(configured[item[0]]).hostname
            and returned.netloc.casefold() == (returned.hostname or "").casefold()
        ]
        filenames = {
            name.casefold() for name in [
                unquote(returned.path.rsplit("/", 1)[-1]),
                result.title or "",
                *(value for key, value in parse_qsl(returned.query) if key.casefold() == "file"),
            ]
            if name and "/" not in name and "\\" not in name
        }
        filename_matches = [
            item for url, item in allowed.items()
            if returned.scheme == "https"
            and not returned.username and not returned.password
            and returned.hostname == urlparse(url).hostname
            and returned.netloc.casefold() == (returned.hostname or "").casefold()
            and unquote(urlparse(url).path.rsplit("/", 1)[-1]).casefold() in filenames
        ]
        matches = {item[0]: item for item in [*url_matches, *identity_matches, *filename_matches]}
        match = next(iter(matches.values())) if len(matches) == 1 else None
        expected = identities.get(match[0]) if match else None
        conflicting_identity = expected and (
            (result.drive_id is not None and result.drive_id != expected["driveId"])
            or (result.item_id is not None and result.item_id != expected["itemId"])
        )
        if match is None or conflicting_identity:
            digest = hashlib.sha256(str(result.url).encode()).hexdigest()[:12]
            logger.warning(
                "Work IQ source identity rejected: diagnostic=%s same_host=%s known_filename=%s "
                "viewer_link=%s has_query=%s has_drive_id=%s has_item_id=%s identity_conflict=%s",
                digest,
                any(returned.hostname == urlparse(url).hostname for url in allowed),
                ",".join(sorted(item[0] for item in filename_matches)) or "none",
                "/_layouts/" in returned.path.casefold(), bool(returned.query),
                bool(result.drive_id), bool(result.item_id), bool(conflicting_identity),
            )
            raise FundingDataUnavailable(
                f"Work IQ returned an unverified or out-of-scope source "
                f"(diagnostic {digest}); no fallback was used."
            )
        document_id, document = match
        if result.url != configured[document_id]:
            logger.warning(
                "Work IQ source URL variant accepted: document=%s matched_by=%s",
                document_id, (
                    "drive_item_identity" if identity_matches
                    else "canonical_path" if url_matches else "filename"
                ),
            )
        reference_ids[result.citation_id] = document_id
        label = result.sensitivity_label.get("displayName")
        citations[document_id] = Evidence(
            refId=document_id,
            source=Source.WORK,
            title=document["title"],
            snippet=" ".join(result.markdown.split())[:600],
            url=result.url,
            sourceType=(
                "Live Work IQ retrieved grounding from synthetic M365 sources; not a verbatim excerpt"
                + ("; matched by filename" if not identity_matches and not url_matches else "")
                + (f"; sensitivity: {label}" if isinstance(label, str) and label else "")
            ),
        )

    def replace_reference(match: re.Match[str]) -> str:
        document_id = reference_ids.get(match.group(1))
        if document_id is None:
            raise FundingDataUnavailable("Work IQ grounding contains an unknown citation.")
        return f"[{document_id}]"

    grounding = "\n\n".join(
        f"[{reference_ids[item.citation_id]}]\n{item.markdown}" for item in answer.documents
    )
    grounding = re.sub(r"\[\^([^\]]+)\]", replace_reference, grounding)
    return FundingWork(grounding, list(citations.values()), query, answer.duration_ms)
