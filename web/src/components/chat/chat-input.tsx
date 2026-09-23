import { useState, type FormEvent } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

export function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (content: string) => void;
  disabled: boolean;
}) {
  const [value, setValue] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!value.trim() || disabled) return;
    onSend(value.trim());
    setValue("");
  }

  return (
    <form onSubmit={submit} className="border-t border-border">
      <div className="mx-auto flex max-w-2xl gap-2 px-4 py-3">
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Escreva sua mensagem..."
          disabled={disabled}
        />
        <Button type="submit" disabled={disabled || !value.trim()}>
          Enviar
        </Button>
      </div>
    </form>
  );
}
