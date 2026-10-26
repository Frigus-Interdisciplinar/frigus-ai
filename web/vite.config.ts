import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  // Token do /metrics lido do .env da raiz (o mesmo da API). Só o proxy do dev server o conhece e o
  // injeta: ele não vai pro bundle nem pro navegador.
  const metricsToken = loadEnv(mode, "..", "").API_KEYS__METRICS_TOKEN;
  const api = "http://127.0.0.1:8000";

  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        // 127.0.0.1, não "localhost": no Windows o Node resolve localhost pra ::1 (IPv6)
        // primeiro, mas a API sobe com host="0.0.0.0" (só IPv4) → ECONNREFUSED → o proxy do
        // Vite responde 502. Ver main.py (uvicorn.run).
        //
        // Rotas de domínio ficam sob /v1 (ver api/app.py); health/metrics na raiz; /keys é o
        // cadastro de API key usado pela tela de login.
        "/v1": api,
        "/keys": api,
        "/health": api,
        "/metrics": {
          target: api,
          headers: metricsToken ? { Authorization: `Bearer ${metricsToken}` } : {},
        },
      },
    },
  };
});
