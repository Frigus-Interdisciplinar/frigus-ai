import type { ReactNode } from "react";

/**
 * O painel web roda com `API__KEY_AUTH_ENABLED=false`: toda request resolve pro usuário local,
 * sem header. O login de usuário (Firebase, `Authorization: Bearer`) é feito pelo app Frigus.
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
