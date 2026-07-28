"""
scraper.extractors.xpath_extractor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Extract data from HTML pages using XPath expressions (via lxml).

Useful for portals with deeply nested or attribute-rich DOM structures
where CSS selectors are insufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TYPE_CHECKING, Union

from lxml import etree, html

from scraper.extractors.base import AbstractExtractor
from scraper.utils.logging import get_logger

if TYPE_CHECKING:
    from scraper.backends.base import PageResponse

logger = get_logger(__name__)


@dataclass
class XPathRule:
    """Configuration for a single XPath extraction rule.

    Attributes:
        expression: XPath expression (must return a list of nodes or strings).
        multiple:   Return all matches as a list instead of the first.
        default:    Value returned when no match is found.
        transform:  Optional callable applied to each extracted string value.
    """

    expression: str
    multiple: bool = False
    default: Any = None
    transform: Callable[[str], Any] | None = None


RuleSpec = Union[str, XPathRule]


def _as_rule(spec: RuleSpec) -> XPathRule:
    return spec if isinstance(spec, XPathRule) else XPathRule(expression=spec)


def _node_text(node: Any) -> str:
    if isinstance(node, str):
        return node.strip()
    if isinstance(node, etree._Element):  # type: ignore[attr-defined]
        return (node.text_content() if hasattr(node, "text_content") else etree.tostring(node, method="text", encoding="unicode")).strip()
    return str(node).strip()


class XPathExtractor(AbstractExtractor):
    """Extract structured data from HTML using XPath expressions.

    Parameters:
        rules: Mapping of ``field_name → xpath_or_rule``.

    Example::

        from scraper.extractors import XPathExtractor, XPathRule

        extractor = XPathExtractor(rules={
            "title":  "//h1/text()",
            "prices": XPathRule("//span[@class='price']/text()", multiple=True),
        })
    """

    def __init__(self, rules: dict[str, RuleSpec]) -> None:
        self._rules: dict[str, XPathRule] = {k: _as_rule(v) for k, v in rules.items()}

    async def extract(self, page: "PageResponse") -> dict[str, Any]:
        try:
            tree = html.fromstring(page.content)
        except Exception as exc:  # noqa: BLE001
            logger.error("XPathExtractor: failed to parse HTML: %s", exc)
            return {}

        result: dict[str, Any] = {}
        for field_name, rule in self._rules.items():
            try:
                matches = tree.xpath(rule.expression)
                if not matches:
                    result[field_name] = rule.default
                    continue

                if rule.multiple:
                    values = [_node_text(m) for m in matches]
                    result[field_name] = (
                        [rule.transform(v) for v in values] if rule.transform else values
                    )
                else:
                    raw = _node_text(matches[0])
                    result[field_name] = rule.transform(raw) if rule.transform else raw

            except Exception as exc:  # noqa: BLE001
                logger.warning("XPathExtractor: error on field '%s': %s", field_name, exc)
                result[field_name] = rule.default

        return result
