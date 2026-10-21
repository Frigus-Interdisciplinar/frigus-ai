"""Leitura de foto enviada por multipart, igual pro `/stock/foto` e pro chat."""

from fastapi import HTTPException, UploadFile, status

MAX_FOTO_BYTES = 8 * 1024 * 1024


async def ler_foto(foto: UploadFile) -> bytes:
    if not (foto.content_type or "").startswith("image/"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Envie uma imagem.")

    # Lê no máximo 1 byte além do limite: arquivo grande não entra inteiro na RAM.
    conteudo = await foto.read(MAX_FOTO_BYTES + 1)
    if len(conteudo) > MAX_FOTO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Foto maior que 8MB.")

    return conteudo


__all__ = ["MAX_FOTO_BYTES", "ler_foto"]
