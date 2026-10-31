"""Incremental, tolerant Server-Sent Events parser.

Implements the WHATWG event-stream rules that matter for LLM APIs:

* ``\\n``, ``\\r\\n`` and bare ``\\r`` line endings, including a ``\\r\\n`` split
  across two network chunks;
* lines split across chunks are buffered until complete;
* ``:`` comment lines (keep-alives such as ``: ping``) are skipped;
* multiple ``data:`` lines in one event are joined with ``\\n``;
* one optional space after the colon is stripped;
* blank events (keep-alive blank lines) are not dispatched.

The ``[DONE]`` sentinel is a provider convention, not SSE, so it is passed
through as ordinary data for the provider to interpret.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Iterator


@dataclass(frozen=True, slots=True)
class SSEEvent:
    """One dispatched server-sent event."""

    data: str
    event: str = "message"
    id: str | None = None


class SSEDecoder:
    """Feed text chunks in, get complete events out."""

    __slots__ = ("_buffer", "_data", "_event", "_id", "_pending_cr")

    def __init__(self) -> None:
        self._buffer = ""
        self._data: list[str] = []
        self._event = ""
        self._id: str | None = None
        self._pending_cr = False

    def feed(self, chunk: str) -> Iterator[SSEEvent]:
        """Consume a chunk and yield every event it completes."""
        if self._pending_cr and chunk.startswith("\n"):
            chunk = chunk[1:]  # second half of a \r\n split across chunks
        self._pending_cr = False
        self._buffer += chunk

        while True:
            idx_n = self._buffer.find("\n")
            idx_r = self._buffer.find("\r")
            if idx_n == -1 and idx_r == -1:
                return
            if idx_r != -1 and (idx_n == -1 or idx_r < idx_n):
                line = self._buffer[:idx_r]
                if idx_r + 1 < len(self._buffer):
                    skip = 2 if self._buffer[idx_r + 1] == "\n" else 1
                else:
                    skip = 1
                    self._pending_cr = True
                self._buffer = self._buffer[idx_r + skip :]
            else:
                line = self._buffer[:idx_n]
                self._buffer = self._buffer[idx_n + 1 :]
            event = self._process_line(line)
            if event is not None:
                yield event

    def flush(self) -> Iterator[SSEEvent]:
        """End of stream: process a final unterminated line and pending event.

        Strict SSE discards an event that lacks its blank-line terminator; LLM
        servers that close the socket right after the last ``data:`` line are
        common enough that we dispatch it instead.
        """
        if self._buffer:
            line, self._buffer = self._buffer, ""
            event = self._process_line(line)
            if event is not None:
                yield event
        event = self._dispatch()
        if event is not None:
            yield event

    def _process_line(self, line: str) -> SSEEvent | None:
        if line == "":
            return self._dispatch()
        if line.startswith(":"):
            return None  # comment / keep-alive
        field, sep, value = line.partition(":")
        if not sep:
            value = ""
        elif value.startswith(" "):
            value = value[1:]
        if field == "data":
            self._data.append(value)
        elif field == "event":
            self._event = value
        elif field == "id" and "\0" not in value:
            self._id = value
        # "retry" and unknown fields are ignored per spec.
        return None

    def _dispatch(self) -> SSEEvent | None:
        if not self._data:
            self._event = ""
            return None
        event = SSEEvent(data="\n".join(self._data), event=self._event or "message", id=self._id)
        self._data = []
        self._event = ""
        return event


async def iter_sse(chunks: AsyncIterable[str]) -> AsyncIterator[SSEEvent]:
    """Decode an async stream of text chunks into SSE events."""
    decoder = SSEDecoder()
    async for chunk in chunks:
        for event in decoder.feed(chunk):
            yield event
    for event in decoder.flush():
        yield event
