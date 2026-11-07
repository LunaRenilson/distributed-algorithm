"""Implementação do Relógio Lógico de Lamport para ordenação causal e total de eventos.

O relógio lógico de Lamport associa a cada evento um número inteiro monotônico crescente.
Ele permite estabelecer uma relação de precedência causal ("aconteceu antes" / happened-before).
Para resolver empates e garantir ordem total estrita, utiliza-se a tupla (clock, node_id),
onde node_id serve como critério de desempate determinístico lexicográfico.
"""

import threading
from dataclasses import dataclass
from typing import Any


@dataclass(order=True, frozen=True)
class LamportTimestamp:
    """Representa um timestamp de Lamport imutável com desempate determinístico.

    Atributos:
        clock (int): Valor escalar do relógio lógico do nó emissor.
        node_id (str): Identificador único do nó que gerou o timestamp,
            utilizado como critério de desempate lexicográfico para ordem total.
    """
    clock: int
    node_id: str


@dataclass
class OrderedEvent:
    """Representa um evento registrado no sistema associado ao seu timestamp de Lamport.

    Atributos:
        event_id (str): Identificador único do evento.
        timestamp (LamportTimestamp): Timestamp que define a posição do evento na ordem causal.
        payload (dict[str, Any]): Dados arbitrários de negócio contidos no evento.
    """
    event_id: str
    timestamp: LamportTimestamp
    payload: dict[str, Any]


class LamportClock:
    """Relógio lógico de Lamport com suporte a concorrência multithread.

    Garante as duas propriedades fundamentais de Lamport:
    1. Avanço local: antes de registrar um evento local, incrementa o relógio em 1.
    2. Atualização causal: ao receber uma mensagem contendo um timestamp remoto t_msg,
       atualiza o relógio para max(clock_local, t_msg) + 1.
    """

    def __init__(self, node_id: str, initial_clock: int = 0) -> None:
        """Inicializa o relógio lógico para o nó especificado.

        Args:
            node_id (str): Identificador único do nó (ex.: 'api-coordinator', 'node-1').
            initial_clock (int, opcional): Valor numérico inicial do contador. Padrão é 0.
        """
        self.node_id = str(node_id)
        self._clock = initial_clock
        self._lock = threading.Lock()

    @property
    def value(self) -> int:
        """Obtém o valor escalar atual do relógio de forma thread-safe."""
        with self._lock:
            return self._clock

    def tick(self) -> LamportTimestamp:
        """Avança o relógio para representar um novo evento interno ou de emissão local.

        Incrementa o contador local em 1 e retorna o LamportTimestamp correspondente.

        Returns:
            LamportTimestamp: O novo timestamp de Lamport após o incremento.
        """
        with self._lock:
            self._clock += 1
            return LamportTimestamp(clock=self._clock, node_id=self.node_id)

    def update(self, received_clock: int) -> LamportTimestamp:
        """Atualiza o relógio lógico ao receber um evento ou mensagem de outro nó.

        Aplica a regra de Lamport: clock = max(clock_local, received_clock) + 1.

        Args:
            received_clock (int): Valor do relógio lógico transportado na mensagem recebida.

        Returns:
            LamportTimestamp: O novo timestamp local após a sincronização causal.
        """
        with self._lock:
            self._clock = max(self._clock, received_clock) + 1
            return LamportTimestamp(clock=self._clock, node_id=self.node_id)

    def current_timestamp(self) -> LamportTimestamp:
        """Consulta o timestamp atual do nó sem avançar o contador.

        Returns:
            LamportTimestamp: O timestamp refletindo o estado atual do relógio.
        """
        with self._lock:
            return LamportTimestamp(clock=self._clock, node_id=self.node_id)
