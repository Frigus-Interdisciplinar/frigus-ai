from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class UserProfileDocument:
    """
    Apenas o perfil comportamental gerado pela IA, chaveado pelo `users.id` do
    Postgres. Identidade (nome, e-mail, senha) já mora inteiramente no Postgres
    — não duplicamos isso aqui.
    """

    user_id:    int
    profile:    str      = field(default="")
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
