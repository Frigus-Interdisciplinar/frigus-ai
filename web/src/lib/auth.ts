// Sessão do painel: a API key fica no localStorage e vai em `X-API-Key` (ver `lib/api.ts`).
// O login de usuário por Firebase é do app Frigus; o painel usa a key emitida por `POST /keys`.
const CHAVE_API = "frigus_api_key";
const CHAVE_METRICAS = "frigus_metrics_token";

function ler(chave: string): string | null {
  try {
    return localStorage.getItem(chave);
  } catch {
    return null;
  }
}

function gravar(chave: string, valor: string | null): void {
  try {
    if (valor) localStorage.setItem(chave, valor);
    else localStorage.removeItem(chave);
  } catch {
    // navegador sem storage: a sessão vale só até recarregar
  }
}

export const getApiKey = () => ler(CHAVE_API);
export const setApiKey = (key: string) => gravar(CHAVE_API, key);
export const clearApiKey = () => gravar(CHAVE_API, null);

// `/metrics` usa outro segredo (Bearer do Prometheus), não a API key do usuário.
export const getMetricsToken = () => ler(CHAVE_METRICAS);
export const setMetricsToken = (token: string) => gravar(CHAVE_METRICAS, token);
