"""Detector de Falhas baseado em Heartbeat periódicos e timeouts adaptáveis.

Algoritmo de detecção de falha onde nós emitem sinais de vida (heartbeat/ping)
periodicamente. Se um nó não responder após um número máximo configurável de tentativas
consecutivas (max_missed), ele é declarado como inoperante ou suspeito (is_alive = False).
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass
class HeartbeatStatus:
    """Estrutura que armazena a telemetria e o estado de saúde de um nó monitorado.

    Atributos:
        node_id (str): Identificador do nó.
        is_alive (bool): Indica se o nó é considerado operacional.
        last_seen (float | None): Timestamp epoch do último heartbeat bem-sucedido.
        missed_count (int): Contagem contínua de pings não respondidos.
        latency_ms (float | None, opcional): Tempo de resposta do último ping em milissegundos.
    """
    node_id: str
    is_alive: bool
    last_seen: float | None
    missed_count: int
    latency_ms: float | None = None


class HeartbeatFailureDetector:
    """Implementa o monitoramento ativo de nós distribuídos via heartbeat com checagem de timeout.

    Permite identificar falhas de comunicação, travamentos de processos ou partições de rede.
    """

    def __init__(
        self,
        nodes: list[str],
        ping_fn: Callable[[str], Awaitable[bool]],
        interval_seconds: float = 2.0,
        timeout_seconds: float = 1.5,
        max_missed: int = 3,
    ) -> None:
        """Inicializa o detector de falhas por heartbeat.

        Args:
            nodes (list[str]): Lista de nós que devem ser monitorados.
            ping_fn (Callable): Função assíncrona ping_fn(node_id) -> bool que executa a sondagem.
            interval_seconds (float, opcional): Intervalo entre cada rodada de sondagem. Padrão é 2.0s.
            timeout_seconds (float, opcional): Timeout limite para cada resposta de ping. Padrão é 1.5s.
            max_missed (int, opcional): Número tolerado de pings perdidos antes de marcar como morto. Padrão é 3.
        """
        self.nodes = list(nodes)
        self.ping_fn = ping_fn
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds
        self.max_missed = max_missed

        self.status: dict[str, HeartbeatStatus] = {
            node: HeartbeatStatus(node_id=node, is_alive=True, last_seen=time.time(), missed_count=0)
            for node in self.nodes
        }
        self._running = False
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Inicia a rotina assíncrona periódica de monitoramento em segundo plano."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        """Interrompe graciosamente o loop de monitoramento."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def check_node(self, node_id: str) -> bool:
        """Sonda individualmente um nó e atualiza seu registro de saúde.

        Calcula a latência em milissegundos se houver sucesso. Caso o nó falhe consecutivamente
        por max_missed vezes, seu status passa para is_alive = False.

        Args:
            node_id (str): Identificador do nó a ser verificado.

        Returns:
            bool: True se o nó ainda for considerado vivo, False caso contrário.
        """
        start_t = time.perf_counter()
        try:
            ok = await asyncio.wait_for(self.ping_fn(node_id), timeout=self.timeout_seconds)
            latency = (time.perf_counter() - start_t) * 1000
        except Exception:
            ok = False
            latency = None

        async with self._lock:
            st = self.status.get(node_id)
            if not st:
                st = HeartbeatStatus(node_id=node_id, is_alive=False, last_seen=None, missed_count=0)
                self.status[node_id] = st

            if ok:
                st.is_alive = True
                st.last_seen = time.time()
                st.missed_count = 0
                st.latency_ms = round(latency, 2) if latency is not None else None
            else:
                st.missed_count += 1
                if st.missed_count >= self.max_missed:
                    st.is_alive = False
                    st.latency_ms = None
            return st.is_alive

    async def _monitor_loop(self) -> None:
        """Loop contínuo de background que dispara sondagens para todos os nós."""
        while self._running:
            tasks = [self.check_node(node) for node in self.nodes]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(self.interval_seconds)

    def is_alive(self, node_id: str) -> bool:
        """Consulta rapidamente de forma síncrona se um nó está operacional no momento.

        Args:
            node_id (str): Identificador do nó consultado.

        Returns:
            bool: True se operacional, False se inoperante ou desconhecido.
        """
        st = self.status.get(node_id)
        return st.is_alive if st else False

    def get_summary(self) -> list[dict]:
        """Gera uma lista com o resumo de saúde e métricas de todos os nós monitorados.

        Returns:
            list[dict]: Lista de dicionários contendo node_id, is_alive, last_seen, missed_count e latency_ms.
        """
        return [
            {
                "node_id": s.node_id,
                "is_alive": s.is_alive,
                "last_seen": s.last_seen,
                "missed_count": s.missed_count,
                "latency_ms": s.latency_ms,
            }
            for s in self.status.values()
        ]
