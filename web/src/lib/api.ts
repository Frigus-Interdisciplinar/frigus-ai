import type { ChatSummary, ExecutionEvent, Fatos, Message } from "../types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...init?.headers,
  };

  const res = await fetch(path, { ...init, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.detail ?? `Erro ${res.status}`, res.status);
  }

  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

export function listChats(): Promise<ChatSummary[]> {
  return request("/chats");
}

export function createChat(): Promise<{ chat_id: string }> {
  return request("/chats", { method: "POST" });
}

export function getMessages(chatId: string): Promise<Message[]> {
  return request(`/chats/${chatId}/messages`);
}

export function sendMessage(
  chatId: string,
  content: string,
): Promise<{ chat_id: string; content: string }> {
  return request(`/chats/${chatId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

// Parser de SSE: eventos vêm como blocos "event: <tipo>\ndata: <json>\n\n" (fastapi.sse).
export async function streamMessage(
  chatId: string,
  content: string,
  onEvent: (evento: ExecutionEvent) => void,
): Promise<void> {
  const res = await fetch(`/chats/${chatId}/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });

  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.detail ?? `Erro ${res.status}`, res.status);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminado = false;

  const consumirBloco = (bloco: string) => {
    const dataLine = bloco.split("\n").find((l) => l.startsWith("data:"));
    if (!dataLine) return;
    const evento = JSON.parse(dataLine.slice(5).trim()) as ExecutionEvent;
    onEvent(evento);
    // Não dá pra confiar só no reader chegar a `done` — o servidor pode manter a conexão SSE
    // aberta depois do generator terminar (keep-alive), o que travava o front em "pensando"
    // pra sempre mesmo com o backend já tendo respondido. run_finished/run_failed é quem marca
    // o fim de verdade, então encerra a leitura assim que um dos dois chega.
    if (evento.type === "run_finished" || evento.type === "run_failed") terminado = true;
  };

  while (!terminado) {
    const { done, value } = await reader.read();

    if (done) {
      // Fechar a conexão logo após o último evento, sem "\n\n" final, é um jeito válido de
      // terminar um SSE — sem isso, o último evento ficava preso no buffer e era descartado.
      buffer += decoder.decode();
      if (buffer.trim()) consumirBloco(buffer);
      break;
    }

    buffer += decoder.decode(value, { stream: true });

    let sep;
    while (!terminado && (sep = buffer.indexOf("\n\n")) !== -1) {
      consumirBloco(buffer.slice(0, sep));
      buffer = buffer.slice(sep + 2);
    }
  }

  await reader.cancel().catch(() => {});
}

export async function getFatos(): Promise<Fatos | null> {
  try {
    return await request<Fatos>("/profile");
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export function saveFatos(fatos: Fatos): Promise<Fatos> {
  return request("/profile", { method: "PUT", body: JSON.stringify(fatos) });
}
