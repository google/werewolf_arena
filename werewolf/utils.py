# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
