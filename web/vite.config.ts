import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // 127.0.0.1, não "localhost": no Windows o Node resolve localhost pra ::1 (IPv6)
      // primeiro, mas a API sobe com host="0.0.0.0" (só IPv4) → ECONNREFUSED → o proxy do
      // Vite responde 502. Ver main.py (uvicorn.run).
      //
      // Rotas de domínio ficam sob /v1 (ver api/app.py); health/metrics na raiz.
      "/v1": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/metrics": "http://127.0.0.1:8000",
    },
  },
});
