import re
import unicodedata

_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")

# Parenthetical/bracketed qualifiers that describe a *different edition* of
# the same recording, not the recording's identity itself. We deliberately
# do NOT strip these before matching — "Song (Live)" and "Song (Studio)" are
# meant to resolve to different canonical recordings per V2 §8 ("support
# remixes, live versions, edits... as distinct canonical entities"). This
# constant exists so callers can be explicit that qualifier-stripping was a
# conscious non-decision, not an oversight.
PRESERVE_EDITION_QUALIFIERS = True


def _strip_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_text(value: str) -> str:
    """Lowercase, diacritic-stripped, punctuation-stripped, whitespace-
    collapsed form used for both title and artist matching. Deliberately
    conservative: it does not remove parenthetical qualifiers (see
    PRESERVE_EDITION_QUALIFIERS) because those often distinguish genuinely
    different recordings, not just formatting noise.
    """
    text = _strip_diacritics(value)
    text = text.lower()
    text = _PUNCTUATION_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def normalize_title(title: str) -> str:
    return normalize_text(title)


def normalize_artist(name: str) -> str:
    return normalize_text(name)


def normalize_artist_credit(artist_names: list[str]) -> str:
    """Order-preserving join so 'A & B' and 'B & A' remain distinguishable
    (MusicBrainz credit order carries meaning — primary artist first).
    """
    return " & ".join(normalize_artist(name) for name in artist_names)
