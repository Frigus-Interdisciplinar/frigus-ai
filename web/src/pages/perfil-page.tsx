import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { ApiError, getFatos, saveFatos } from "../lib/api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import type { Fatos } from "../types";

const CONTROL =
  "w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring";

const CAMPOS: { chave: keyof Fatos; label: string; placeholder: string }[] = [
  { chave: "alergias", label: "alergias", placeholder: "lactose\namendoim" },
  { chave: "restricoes", label: "restrições", placeholder: "vegetariano\nsem glúten" },
  { chave: "preferencias", label: "preferências", placeholder: "comida caseira\nfrango" },
  { chave: "habitos", label: "hábitos", placeholder: "almoça fora 3x por semana" },
];

const FATOS_VAZIOS: Fatos = { alergias: [], preferencias: [], restricoes: [], habitos: [] };

function linhasParaLista(texto: string): string[] {
  return texto
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

function listaParaLinhas(lista: string[]): string {
  return lista.join("\n");
}

export function PerfilPage() {
  const [fatos, setFatos] = useState<Fatos>(FATOS_VAZIOS);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [status, setStatus] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);

  useEffect(() => {
    getFatos()
      .then((f) => {
        if (f) setFatos(f);
      })
      .catch(() => setStatus({ tipo: "erro", texto: "Não consegui carregar o perfil atual." }))
      .finally(() => setCarregando(false));
  }, []);

  async function salvar(e: FormEvent) {
    e.preventDefault();
    if (salvando) return;

    setSalvando(true);
    setStatus(null);

    try {
      const salvo = await saveFatos(fatos);
      setFatos(salvo);
      setStatus({ tipo: "ok", texto: "Perfil salvo. O Frigus.AI usa esses dados nas conversas." });
    } catch (err) {
      const texto = err instanceof ApiError ? err.message : "Não consegui falar com a API.";
      setStatus({ tipo: "erro", texto });
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <Card className="mx-auto max-w-xl p-6">
        <header className="mb-6 flex items-baseline justify-between">
          <h1 className="font-display text-xl font-semibold text-foreground">Perfil alimentar</h1>
          <Link to="/chat" className="text-sm text-muted-foreground hover:text-foreground">
            voltar ao chat
          </Link>
        </header>

        <p className="mb-6 text-sm text-muted-foreground">
          Um item por linha. O chat também aprende sozinho ao longo da conversa — mas só
          adiciona alergia, nunca remove: pra tirar uma alergia daqui, é só apagar a linha e
          salvar.
        </p>

        {carregando ? (
          <p className="text-sm text-muted-foreground">Carregando...</p>
        ) : (
          <form onSubmit={salvar} className="flex flex-col gap-4">
            {CAMPOS.map(({ chave, label, placeholder }) => (
              <label key={chave} className="flex flex-col gap-1.5 text-sm font-medium text-foreground">
                {label}
                <textarea
                  rows={3}
                  className={CONTROL}
                  value={listaParaLinhas(fatos[chave])}
                  onChange={(e) =>
                    setFatos((prev) => ({ ...prev, [chave]: linhasParaLista(e.target.value) }))
                  }
                  placeholder={placeholder}
                />
              </label>
            ))}

            <div className="mt-2 flex items-center justify-between gap-4">
              <p
                className={`text-sm ${
                  status?.tipo === "erro"
                    ? "text-destructive"
                    : status?.tipo === "ok"
                      ? "text-foreground"
                      : "text-muted-foreground"
                }`}
              >
                {status?.texto ?? "nada salvo ainda nesta sessão"}
              </p>
              <Button type="submit" disabled={salvando}>
                {salvando ? "salvando..." : "salvar perfil"}
              </Button>
            </div>
          </form>
        )}
      </Card>
    </div>
  );
}
