import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { ApiError, criarApiKey, listChats } from "../lib/api";
import { clearApiKey, getApiKey, setApiKey } from "../lib/auth";

type Modo = "entrar" | "criar";

export function LoginPage() {
  const navigate = useNavigate();
  const [modo, setModo] = useState<Modo>("entrar");
  const [chave, setChave] = useState("");
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [segredo, setSegredo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  if (getApiKey()) return <Navigate to="/chat" replace />;

  async function entrar(key: string) {
    // Guarda antes de validar: o `request` lê a key do storage. Se não valer, desfaz.
    setApiKey(key);
    try {
      await listChats();
      navigate("/chat", { replace: true });
    } catch (e) {
      clearApiKey();
      throw e;
    }
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setCarregando(true);

    try {
      if (modo === "entrar") {
        await entrar(chave.trim());
      } else {
        const { api_key } = await criarApiKey(nome.trim(), email.trim(), segredo);
        await entrar(api_key);
      }
    } catch (e) {
      setErro(mensagem(e, modo));
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <Card className="w-full max-w-sm p-6">
        <div className="mb-5 flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary font-display text-sm font-bold text-primary-foreground">
            F
          </span>
          <h1 className="font-display text-lg font-semibold text-foreground">Frigus.AI</h1>
        </div>

        <div className="mb-4 grid grid-cols-2 gap-1 rounded-md bg-muted p-1 text-sm">
          {(["entrar", "criar"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => {
                setModo(m);
                setErro(null);
              }}
              className={`rounded px-3 py-1.5 font-medium ${
                modo === m ? "bg-card text-foreground shadow-sm" : "text-muted-foreground"
              }`}
            >
              {m === "entrar" ? "Entrar" : "Criar chave"}
            </button>
          ))}
        </div>

        <form onSubmit={enviar} className="flex flex-col gap-3">
          {modo === "entrar" ? (
            <label className="flex flex-col gap-1 text-sm text-muted-foreground">
              API key
              <Input
                type="password"
                autoComplete="current-password"
                value={chave}
                onChange={(e) => setChave(e.target.value)}
                placeholder="cole a sua key"
                required
              />
            </label>
          ) : (
            <>
              <label className="flex flex-col gap-1 text-sm text-muted-foreground">
                Nome
                <Input value={nome} onChange={(e) => setNome(e.target.value)} required />
              </label>
              <label className="flex flex-col gap-1 text-sm text-muted-foreground">
                E-mail
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </label>
              <label className="flex flex-col gap-1 text-sm text-muted-foreground">
                Segredo de cadastro
                <Input
                  type="password"
                  value={segredo}
                  onChange={(e) => setSegredo(e.target.value)}
                  required
                />
              </label>
            </>
          )}

          {erro && <p className="text-sm text-destructive">{erro}</p>}

          <Button type="submit" disabled={carregando}>
            {carregando ? "Aguarde…" : modo === "entrar" ? "Entrar" : "Criar e entrar"}
          </Button>
        </form>

        {modo === "criar" && (
          <p className="mt-3 text-xs text-muted-foreground">
            A key é gerada uma vez e guardada neste navegador. Se o e-mail já tem uma key ativa, use
            "Entrar" com ela.
          </p>
        )}
      </Card>
    </div>
  );
}

function mensagem(e: unknown, modo: Modo): string {
  if (e instanceof ApiError) {
    if (e.status === 401) return modo === "entrar" ? "API key inválida." : "Segredo de cadastro inválido.";
    if (e.status === 409) return "Esse e-mail já tem uma key ativa. Entre com ela.";
    if (e.status === 429) return "Muitas tentativas. Tente de novo mais tarde.";
    return e.message;
  }
  return "Não consegui falar com a API.";
}
