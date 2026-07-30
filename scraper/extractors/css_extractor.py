"""
scraper.extractors.css_extractor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Extract data from HTML pages using CSS selectors.

Supports extracting:
- Text content (default)
- Specific attributes (e.g. ``href``, ``src``)
- Lists of values (when *multiple=True*)

Configuration is driven by a *rules* dictionary::

    extractor = CSSExtractor(rules={
        "title":    "h1",
        "price":    ".product-price::text",
        "image":    CSSRule("img.hero", attribute="src"),
        "tags":     CSSRule("ul.tags li", multiple=True),
    })
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING, Union

from bs4 import BeautifulSoup, Tag

from scraper.extractors.base import AbstractExtractor
from scraper.utils.logging import get_logger

if TYPE_CHECKING:
    from scraper.backends.base import PageResponse

logger = get_logger(__name__)


@dataclass
class CSSRule:
    """Configuration for a single CSS extraction rule.

    Attributes:
        selector:   CSS selector string.
        attribute:  HTML attribute to extract (``None`` → text content).
        multiple:   Return a list of all matches instead of just the first.
        default:    Value returned when no element is found.
        transform:  Optional callable applied to the extracted value(s).
    """

    selector: str
    attribute: str | None = None
    multiple: bool = False
    default: Any = None
    transform: Any = None  # Callable[[str], Any]


RuleSpec = Union[str, CSSRule]


def _as_rule(spec: RuleSpec) -> CSSRule:
    return spec if isinstance(spec, CSSRule) else CSSRule(selector=spec)


def _extract_value(tag: Tag, rule: CSSRule) -> str:
    if rule.attribute:
        return tag.get(rule.attribute, "") or ""
    return tag.get_text(strip=True)


class CSSExtractor(AbstractExtractor):
    """Extract structured data from HTML using CSS selectors.

    Parameters:
        rules: Mapping of ``field_name → selector_or_rule``.
               Accepts both plain selector strings and :class:`CSSRule` objects.

    Example::

        from scraper.extractors import CSSExtractor, CSSRule

        extractor = CSSExtractor(rules={
            "title":    "h1.page-title",
            "price":    CSSRule(".price", transform=lambda v: float(v.replace(",", "."))),
            "images":   CSSRule("img", attribute="src", multiple=True),
        })
    """

    def __init__(self, rules: dict[str, RuleSpec]) -> None:
        self._rules: dict[str, CSSRule] = {k: _as_rule(v) for k, v in rules.items()}

    async def extract(self, page: "PageResponse") -> dict[str, Any]:
        soup = BeautifulSoup(page.content, "lxml")
        result: dict[str, Any] = {}

        for field_name, rule in self._rules.items():
            try:
                if rule.multiple:
                    tags = soup.select(rule.selector)
                    values = [_extract_value(t, rule) for t in tags]
                    result[field_name] = (
                        [rule.transform(v) for v in values] if rule.transform else values
                    )
                else:
                    tag = soup.select_one(rule.selector)
                    if tag is None:
                        result[field_name] = rule.default
                    else:
                        raw = _extract_value(tag, rule)
                        result[field_name] = rule.transform(raw) if rule.transform else raw
            except Exception as exc:  # noqa: BLE001
                logger.warning("CSSExtractor: error on field '%s': %s", field_name, exc)
                result[field_name] = rule.default

        return result
