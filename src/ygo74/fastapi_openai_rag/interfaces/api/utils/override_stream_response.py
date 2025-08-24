import typing
from functools import partial

import anyio
from fastapi.responses import StreamingResponse
from starlette.types import Send, Scope, Receive


class OverrideStreamResponse(StreamingResponse):
    """
    Override StreamingResponse to support lazy send response status_code and response headers
    """

    async def stream_response(self, send: Send) -> None:
        import logging
        logger = logging.getLogger(__name__)
        first_chunk = True
        try:
            # Toujours envoyer les en-têtes immédiatement pour les réponses SSE
            # Cela aide les clients à commencer à lire le flux sans attendre le premier chunk
            await self.send_request_header(send)
            first_chunk = False

            # Envoyer un chunk vide pour initier la connexion
            # Ce ping initial est important pour certains clients
            ping = b'\n'
            await send({'type': 'http.response.body', 'body': ping, 'more_body': True})

            async for chunk in self.body_iterator:
                # S'assurer que le chunk est au format bytes
                if isinstance(chunk, str):
                    chunk = chunk.encode(self.charset)
                elif not isinstance(chunk, bytes):
                    # Pour les autres types, convertir en string puis en bytes
                    chunk = str(chunk).encode(self.charset)

                # Log pour déboguer le streaming
                logger.debug(f"Sending chunk: {chunk[:50]}...")

                # Envoyer le chunk avec le drapeau more_body=True
                await send({'type': 'http.response.body', 'body': chunk, 'more_body': True})

                # Petit délai pour laisser le client traiter le chunk
                await anyio.sleep(0.01)

            # Terminer la réponse avec le dernier chunk vide
            logger.debug("Sending final empty chunk to terminate response")
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

        except Exception as e:
            # En cas d'erreur, s'assurer que les en-têtes sont envoyés et terminer la réponse
            logger.error(f"Error in streaming response: {str(e)}", exc_info=True)

            if first_chunk:
                await self.send_request_header(send)

            # Envoyer un message d'erreur au client
            error_msg = f"data: {{\"error\": {{\"message\": \"{str(e)}\", \"type\": \"stream_error\"}}}}\r\n\r\n".encode("utf-8")
            await send({'type': 'http.response.body', 'body': error_msg, 'more_body': True})

            # Terminer la réponse avec [DONE] même en cas d'erreur
            done_msg = b"data: [DONE]\r\n\r\n"
            await send({'type': 'http.response.body', 'body': done_msg, 'more_body': True})

            # Terminer la réponse en cas d'erreur
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

    async def send_request_header(self, send: Send) -> None:
        await send(
            {
                'type': 'http.response.start',
                'status': self.status_code,
                'headers': self.raw_headers,
            }
        )

    async def listen_for_disconnect(self, receive: Receive) -> None:
        message = await receive()
        if message["type"] == "http.disconnect":
            # Client disconnected, cancel the task
            raise anyio.get_cancelled_exc_class()()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async with anyio.create_task_group() as task_group:
            async def wrap(func: typing.Callable[[], typing.Awaitable[None]]) -> None:
                await func()
                task_group.cancel_scope.cancel()

            task_group.start_soon(wrap, partial(self.stream_response, send))
            await wrap(partial(self.listen_for_disconnect, receive))

        if self.background is not None:
            await self.background()