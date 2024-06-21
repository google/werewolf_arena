"""utility functions."""

from typing import Any
import yaml
from abc import ABC
from abc import abstractmethod
import marko


def parse_json(text: str) -> dict[str, Any] | None:
    result_json = parse_json_markdown(text)

    if not result_json:
        result_json = parse_json_str(text)
    return result_json


def parse_json_markdown(text: str) -> dict[str, Any] | None:
    ast = marko.parse(text)

    for c in ast.children:
        # find the first json block (```json or ```JSON)
        if hasattr(c, "lang") and c.lang.lower() == "json":
            json_str = c.children[0].children
            return parse_json_str(json_str)

    return None


def parse_json_str(text: str) -> dict[str, Any] | None:
    try:
        # use yaml.safe_load which handles missing quotes around field names.
        result_json = yaml.safe_load(text)
    except yaml.parser.ParserError:
        return None

    return result_json


class Deserializable(ABC):
    @classmethod
    @abstractmethod
    def from_json(cls, data: dict[Any, Any]):
        pass
