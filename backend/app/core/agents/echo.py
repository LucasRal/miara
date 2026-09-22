"""Agent de test `echo` : valide le runtime sans dépendre d'un module métier.

Deux outils fictifs — une lecture (`echo_read`, renverse un texte) et une
écriture (`echo_note`, simule un enregistrement, donc soumise à confirmation
humaine). Sert aux tests d'intégration et aux démonstrations du chap. 5.
"""

from pydantic import BaseModel, Field

from app.core.agents.context import RequestContext
from app.core.agents.definition import AgentDefinition
from app.core.agents.tool import Tool


class EchoReadArgs(BaseModel):
    text: str = Field(description="Texte à renvoyer inversé")


class EchoNoteArgs(BaseModel):
    note: str = Field(description="Note à enregistrer")


async def _echo_read(args: BaseModel, ctx: RequestContext) -> dict[str, str]:
    assert isinstance(args, EchoReadArgs)
    return {"echo": args.text[::-1]}


async def _echo_note(args: BaseModel, ctx: RequestContext) -> dict[str, str]:
    assert isinstance(args, EchoNoteArgs)
    # Simule une écriture ; l'org viendrait de ctx.org_id, jamais des args.
    return {"stored": args.note, "organization": str(ctx.org_id)}


echo_read = Tool(
    name="echo_read",
    description="Renvoie le texte donné, inversé (outil de lecture).",
    args_schema=EchoReadArgs,
    is_write=False,
    handler=_echo_read,
)

echo_note = Tool(
    name="echo_note",
    description="Enregistre une note (outil d'écriture, confirmation requise).",
    args_schema=EchoNoteArgs,
    is_write=True,
    handler=_echo_note,
)

echo_agent = AgentDefinition(
    name="core.echo",
    model_alias="sales.route",  # alias léger (ADR-011)
    prompt_name="echo",
    tools=[echo_read, echo_note],
)
