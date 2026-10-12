"""Small IFC-SPF parser used by the dependency-light MVP.

This is deliberately not a geometry parser. It extracts entity records and
top-level arguments so QC rules can run before IfcOpenShell is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


ENTITY_RE = re.compile(r"^\s*#(?P<id>\d+)\s*=\s*(?P<type>IFC[A-Z0-9_]+)\s*\((?P<args>.*)\)\s*;\s*$", re.I | re.S)
SCHEMA_RE = re.compile(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", re.I)
REFERENCE_RE = re.compile(r"#(\d+)")


@dataclass(frozen=True)
class Entity:
    step_id: int
    type_name: str
    raw_args: str
    args: tuple[str, ...]

    @property
    def ref(self) -> str:
        return f"#{self.step_id}"

    @property
    def global_id(self) -> str | None:
        if not self.args:
            return None
        value = unquote(self.args[0])
        return value if value and value != "$" else None

    @property
    def name(self) -> str | None:
        if len(self.args) < 3:
            return None
        value = unquote(self.args[2])
        return value if value and value != "$" else None


@dataclass(frozen=True)
class IfcModel:
    schema: str
    entities: tuple[Entity, ...]

    @property
    def by_id(self) -> dict[int, Entity]:
        return {entity.step_id: entity for entity in self.entities}

    def of_type(self, *type_names: str) -> list[Entity]:
        wanted = {name.upper() for name in type_names}
        return [entity for entity in self.entities if entity.type_name in wanted]


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def split_arguments(raw: str) -> tuple[str, ...]:
    """Split a STEP argument list while respecting strings and nesting."""
    values: list[str] = []
    start = 0
    depth = 0
    in_string = False
    index = 0
    while index < len(raw):
        char = raw[index]
        if char == "'":
            if in_string and index + 1 < len(raw) and raw[index + 1] == "'":
                index += 2
                continue
            in_string = not in_string
        elif not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            elif char == "," and depth == 0:
                values.append(raw[start:index].strip())
                start = index + 1
        index += 1
    values.append(raw[start:].strip())
    return tuple(values)


def iter_statements(text: str):
    """Yield semicolon-terminated STEP statements, including multiline ones."""
    start = 0
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == "'":
            if in_string and index + 1 < len(text) and text[index + 1] == "'":
                index += 2
                continue
            in_string = not in_string
        elif char == ";" and not in_string:
            yield text[start : index + 1]
            start = index + 1
        index += 1


def parse_ifc(text: str) -> IfcModel:
    if "ISO-10303-21" not in text.upper():
        raise ValueError("This does not appear to be an IFC STEP file.")

    schema_match = SCHEMA_RE.search(text)
    schema = schema_match.group(1).upper() if schema_match else "UNKNOWN"
    entities: list[Entity] = []
    for statement in iter_statements(text):
        match = ENTITY_RE.match(statement)
        if not match:
            continue
        raw_args = match.group("args")
        entities.append(
            Entity(
                step_id=int(match.group("id")),
                type_name=match.group("type").upper(),
                raw_args=raw_args,
                args=split_arguments(raw_args),
            )
        )
    if not entities:
        raise ValueError("No IFC entities were found in the file.")
    return IfcModel(schema=schema, entities=tuple(entities))


def referenced_ids(entity: Entity) -> set[int]:
    return {int(value) for value in REFERENCE_RE.findall(entity.raw_args)}
