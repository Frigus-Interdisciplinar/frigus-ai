import type { ReactNode } from "react";

/**
 * No assessor-ai original, isso escolhia um usuário aleatório via `X-User-Id` (modo dev sem
 * auth). O Frigus não tem essa troca de usuário: com `API_KEY_AUTH_ENABLED=false`
 * (`api/auth.py`), toda request já resolve pro único usuário local automaticamente, sem
 * header nenhum — não tem o que "entrar" aqui. Fica só como ponto único caso um dia o Frigus
 * ganhe login de verdade (`X-API-Key`).
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
