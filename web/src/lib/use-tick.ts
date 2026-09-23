import { useEffect, useReducer } from "react";

// Força re-render periódico enquanto `active` — usado pra fazer o cronômetro do node em
// execução andar sem precisar guardar "agora" no estado (que reiniciaria o efeito toda hora).
export function useTick(active: boolean, intervalMs = 100): void {
  const [, forceRender] = useReducer((n: number) => n + 1, 0);

  useEffect(() => {
    if (!active) return;
    const id = setInterval(forceRender, intervalMs);
    return () => clearInterval(id);
  }, [active, intervalMs]);
}
