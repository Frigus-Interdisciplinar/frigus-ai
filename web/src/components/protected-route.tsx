import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router";
import { ApiError, listChats } from "../lib/api";
import { getApiKey } from "../lib/auth";

type Sessao = "checando" | "ok" | "login";

/**
 * Deixa passar quem tem sessão válida. Sem key guardada, testa a API: com `API__KEY_AUTH_ENABLED=false`
 * (modo local/demo) ela responde 200 sem credencial e o painel abre direto; com auth ligada responde 401
 * e manda pro /login. Outros erros (API fora do ar) deixam a página abrir, que mostra o próprio erro.
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const [sessao, setSessao] = useState<Sessao>(getApiKey() ? "ok" : "checando");

  useEffect(() => {
    if (sessao !== "checando") return;

    listChats()
      .then(() => setSessao("ok"))
      .catch((e) => setSessao(e instanceof ApiError && e.status === 401 ? "login" : "ok"));
  }, [sessao]);

  if (sessao === "login") return <Navigate to="/login" replace />;
  if (sessao === "checando") return null;

  return <>{children}</>;
}
