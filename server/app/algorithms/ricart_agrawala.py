"""Algoritmo de Exclusão Mútua Distribuída de Ricart-Agrawala.

O algoritmo de Ricart-Agrawala é uma otimização do algoritmo de Lamport para exclusão mútua.
Ele reduz o número de mensagens trocadas exigindo apenas 2*(N-1) mensagens por entrada na
seção crítica (N-1 mensagens REQUEST e N-1 mensagens REPLY).

Estados possíveis de um nó:
- RELEASED: O nó não deseja e não está utilizando a seção crítica. Responde imediatamente a qualquer REQUEST.
- WANTED: O nó solicitou a seção crítica e aguarda autorização (REPLY) de todos os outros pares (peers).
- HELD: O nó obteve permissão de todos os pares e está executando a seção crítica.

Regras de prioridade para resolver conflitos de concorrência:
Se dois nós estão em WANTED simultaneamente, o desempate é feito pelo timestamp de Lamport:
- Prioridade maior = menor timestamp (clock menor ou, em caso de empate, node_id menor).
- O nó com menor prioridade posterga (defere) sua resposta até liberar a seção crítica.
"""

import asyncio
from enum import Enum
from typing import Awaitable, Callable

from app.algorithms.lamport import LamportClock, LamportTimestamp


class NodeState(str, Enum):
    """Representa o estado do nó no ciclo de vida da exclusão mútua distribuída."""
    RELEASED = "RELEASED"
    WANTED = "WANTED"
    HELD = "HELD"


class RicartAgrawalaMutex:
    """Implementa o gerenciamento de exclusão mútua distribuída pelo protocolo de Ricart-Agrawala.

    Permite que múltiplos nós coordenem o acesso exclusivo a um recurso compartilhado
    sem depender de um coordenador centralizado de locks, tolerando desempates determinísticos.
    """

    def __init__(
        self,
        node_id: str,
        peers: list[str],
        clock: LamportClock | None = None,
        send_request_fn: Callable[[str, LamportTimestamp], Awaitable[bool]] | None = None,
        send_reply_fn: Callable[[str], Awaitable[bool]] | None = None,
    ) -> None:
        """Inicializa o mutex de Ricart-Agrawala.

        Args:
            node_id (str): Identificador único deste nó.
            peers (list[str]): Lista de nós participantes com os quais a exclusão mútua é coordenada.
            clock (LamportClock, opcional): Instância do relógio de Lamport compartilhado ou dedicado.
            send_request_fn (Callable, opcional): Função assíncrona responsável por enviar REQUEST a um peer.
            send_reply_fn (Callable, opcional): Função assíncrona responsável por enviar REPLY a um peer.
        """
        self.node_id = str(node_id)
        self.peers = [str(p) for p in peers if str(p) != self.node_id]
        self.clock = clock or LamportClock(node_id=self.node_id)

        self.state = NodeState.RELEASED
        self.request_timestamp: LamportTimestamp | None = None
        self.deferred_replies: set[str] = set()
        self.received_replies: set[str] = set()

        self._lock = asyncio.Lock()
        self._replies_event = asyncio.Event()

        self.send_request_fn = send_request_fn
        self.send_reply_fn = send_reply_fn

    async def request_access(self, timeout_seconds: float = 5.0) -> bool:
        """Solicita autorização distribuída para entrar na seção crítica.

        Muda o estado para WANTED, gera um novo timestamp de Lamport e dispara
        mensagens de REQUEST para todos os nós vizinhos (peers). Bloqueia a execução
        até receber REPLY de todos os pares ou até ocorrer timeout.

        Args:
            timeout_seconds (float, opcional): Tempo limite máximo em segundos para esperar respostas.

        Returns:
            bool: True se o acesso exclusivo foi obtido com sucesso (estado HELD), False em caso de timeout.
        """
        async with self._lock:
            self.state = NodeState.WANTED
            self.request_timestamp = self.clock.tick()
            self.received_replies.clear()
            self._replies_event.clear()

        needed_replies = len(self.peers)
        if needed_replies == 0:
            async with self._lock:
                self.state = NodeState.HELD
            return True

        req_ts = self.request_timestamp

        if self.send_request_fn:
            for peer in self.peers:
                asyncio.create_task(self._safe_send_request(peer, req_ts))

        try:
            await asyncio.wait_for(self._wait_for_replies(needed_replies), timeout=timeout_seconds)
            async with self._lock:
                self.state = NodeState.HELD
            return True
        except asyncio.TimeoutError:
            async with self._lock:
                self.state = NodeState.RELEASED
                self.request_timestamp = None
            return False

    async def _safe_send_request(self, peer: str, ts: LamportTimestamp) -> None:
        """Encapsula o envio de REQUEST a um nó com tratamento defensivo contra exceções de rede."""
        try:
            if self.send_request_fn:
                ok = await self.send_request_fn(peer, ts)
                if ok:
                    await self.receive_reply(peer)
        except Exception:
            pass

    async def _wait_for_replies(self, needed_replies: int) -> None:
        """Aguarda até que o número de respostas recebidas atinja a quantidade de peers necessários."""
        while True:
            async with self._lock:
                if len(self.received_replies) >= needed_replies:
                    return
            await self._replies_event.wait()
            self._replies_event.clear()

    async def receive_request(self, requester_id: str, requester_ts: LamportTimestamp) -> bool:
        """Processa a mensagem de REQUEST recebida de outro nó requerente.

        Atualiza o relógio de Lamport local e decide se concede permissão imediatamente (REPLY)
        ou se posterga (defere) a resposta com base no estado e na prioridade dos timestamps.

        Args:
            requester_id (str): Identificador do nó solicitante.
            requester_ts (LamportTimestamp): Timestamp de Lamport associado ao pedido do solicitante.

        Returns:
            bool: True se o acesso for concedido imediatamente, False se a resposta for postergada.
        """
        async with self._lock:
            self.clock.update(requester_ts.clock)

            my_priority = False
            if self.state in (NodeState.WANTED, NodeState.HELD) and self.request_timestamp:
                my_priority = (self.request_timestamp < requester_ts)

            should_defer = (self.state == NodeState.HELD) or (
                self.state == NodeState.WANTED and my_priority
            )

            if should_defer:
                self.deferred_replies.add(requester_id)
                return False
            else:
                return True

    async def receive_reply(self, from_peer: str) -> None:
        """Registra a confirmação de REPLY recebida de um nó participante.

        Se o nó estiver no estado WANTED, computa o aceite e notifica a espera.

        Args:
            from_peer (str): Identificador do nó que autorizou o acesso.
        """
        async with self._lock:
            if self.state == NodeState.WANTED:
                self.received_replies.add(from_peer)
                self._replies_event.set()

    async def release_access(self) -> list[str]:
        """Libera a seção crítica e desempilha respostas para nós postergados.

        Altera o estado para RELEASED e envia respostas de REPLY a todos os nós que
        estavam na fila de pendências (deferred_replies).

        Returns:
            list[str]: Lista dos identificadores de nós para os quais respostas diferidas foram despachadas.
        """
        async with self._lock:
            self.state = NodeState.RELEASED
            self.request_timestamp = None
            nodes_to_reply = list(self.deferred_replies)
            self.deferred_replies.clear()

        if self.send_reply_fn:
            for peer in nodes_to_reply:
                asyncio.create_task(self._safe_send_reply(peer))

        return nodes_to_reply

    async def _safe_send_reply(self, peer: str) -> None:
        """Encapsula o envio de REPLY diferido a um nó com proteção contra falhas de transporte."""
        try:
            if self.send_reply_fn:
                await self.send_reply_fn(peer)
        except Exception:
            pass
