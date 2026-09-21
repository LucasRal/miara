"""CRM simulé en mémoire (tests d'interface, mode démo sans Salesforce).

Implémente le même contrat que `SalesforceClient` sur un sous-ensemble SOQL
suffisant pour les outils d'agent :

    SELECT <champs|*> FROM <Objet>
      [WHERE <cond> (AND <cond>)*]
      [ORDER BY <champ> [ASC|DESC]]
      [LIMIT <n>]

où <cond> = <champ> <op> <valeur>, op ∈ { = != >= <= > < LIKE }. Les valeurs
sont soit '...' (chaîne), soit un littéral non quoté (nombre, booléen, date
ISO). Les dates/nombres se comparent comme des chaînes (l'ISO se trie bien).
"""

import itertools
import re
from typing import Any

from app.sales.crm.port import CRMError

_QUERY = re.compile(
    r"^\s*SELECT\s+(?P<fields>.+?)\s+FROM\s+(?P<object>\w+)"
    r"(?:\s+WHERE\s+(?P<where>.+?))?"
    r"(?:\s+ORDER\s+BY\s+(?P<order_field>[\w.]+)(?:\s+(?P<order_dir>ASC|DESC))?)?"
    r"(?:\s+LIMIT\s+(?P<limit>\d+))?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_COND = re.compile(
    r"^\s*(?P<field>[\w.]+)\s*(?P<op>LIKE|!=|>=|<=|=|>|<)\s*(?P<value>'[^']*'|\S+)\s*$",
    re.IGNORECASE,
)


def _split_and(clause: str) -> list[str]:
    """Découpe sur ` AND ` en dehors des chaînes quotées."""
    parts: list[str] = []
    current = ""
    in_quote = False
    i = 0
    while i < len(clause):
        if clause[i] == "'":
            in_quote = not in_quote
            current += clause[i]
            i += 1
        elif not in_quote and clause[i : i + 5].upper() == " AND ":
            parts.append(current.strip())
            current = ""
            i += 5
        else:
            current += clause[i]
            i += 1
    parts.append(current.strip())
    return parts


def _unquote(value: str) -> str:
    return value[1:-1] if len(value) >= 2 and value[0] == "'" and value[-1] == "'" else value


def _like(text: str, pattern: str) -> bool:
    t, p = text.lower(), pattern.lower()
    if p.startswith("%") and p.endswith("%"):
        return p.strip("%") in t
    if p.startswith("%"):
        return t.endswith(p[1:])
    if p.endswith("%"):
        return t.startswith(p[:-1])
    return t == p


def _matches(record: dict[str, Any], field: str, op: str, value: str) -> bool:
    raw = record.get(field)
    op = op.upper()
    if op == "LIKE":
        return _like(str(raw or ""), value)
    if op == "=":
        return str(raw).lower() == value.lower()
    if op == "!=":
        return str(raw).lower() != value.lower()
    if raw is None:
        return False
    left, right = str(raw), value
    return {
        ">=": left >= right,
        "<=": left <= right,
        ">": left > right,
        "<": left < right,
    }[op]


class FakeCRM:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, dict[str, Any]]] = {}
        self._ids = itertools.count(1)

    def _table(self, object: str) -> dict[str, dict[str, Any]]:
        return self._store.setdefault(object, {})

    async def query(self, soql: str) -> list[dict[str, Any]]:
        match = _QUERY.match(soql)
        if match is None:
            raise CRMError(f"SOQL non supporté par FakeCRM : {soql!r}")
        rows = list(self._table(match["object"]).values())

        if match["where"]:
            for part in _split_and(match["where"]):
                cond = _COND.match(part)
                if cond is None:
                    raise CRMError(f"Condition SOQL non supportée : {part!r}")
                field, op, value = cond["field"], cond["op"], _unquote(cond["value"])
                rows = [r for r in rows if _matches(r, field, op, value)]

        if match["order_field"]:
            rows.sort(
                key=lambda r: str(r.get(match["order_field"]) or ""),
                reverse=(match["order_dir"] or "").upper() == "DESC",
            )
        if match["limit"]:
            rows = rows[: int(match["limit"])]

        fields = [f.strip() for f in match["fields"].split(",")]
        if fields == ["*"]:
            return [dict(r) for r in rows]
        return [{f: r.get(f) for f in fields} for r in rows]

    async def get(self, object: str, id: str) -> dict[str, Any]:
        record = self._table(object).get(id)
        if record is None:
            raise CRMError(f"Erreur Salesforce 404 : {object} {id} introuvable")
        return dict(record)

    async def create(self, object: str, data: dict[str, Any]) -> str:
        id = f"FAKE{next(self._ids):015d}"
        self._table(object)[id] = {"Id": id, **data}
        return id

    async def update(self, object: str, id: str, data: dict[str, Any]) -> None:
        record = self._table(object).get(id)
        if record is None:
            raise CRMError(f"Erreur Salesforce 404 : {object} {id} introuvable")
        record.update(data)

    async def aclose(self) -> None:
        return None
