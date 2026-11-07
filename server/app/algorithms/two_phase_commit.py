"""Protocolo de Compromisso Atômico Two-Phase Commit (2PC).

Garante atomicidade estrita ("tudo ou nada") em transações distribuídas entre
múltiplos nós ou participantes heterogêneos.

Fases do Protocolo:
1. PREPARE (Votação):
   - O Coordenador solicita PREPARE a todos os participantes.
   - Cada participante verifica suas condições locais (recursos, integridade, travas)
     e responde com seu voto: YES (pronto para efetivar) ou NO (impossível efetivar).
2. DECISÃO (Efetivação ou Cancelamento):
   - Se TODOS os participantes votarem YES, o Coordenador decide e emite COMMIT.
   - Se qualquer participante votar NO ou se ocorrer timeout/falha, o Coordenador decide e emite ABORT.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable


class TxState(str, Enum):
    """Estados possíveis de uma transação no ciclo do Two-Phase Commit."""
    INIT = "INIT"
    PREPARING = "PREPARING"
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass
class TxRecord:
    """Registro estruturado de transação gerenciado por coordenador ou participante.

    Atributos:
        tx_id (str): Identificador único global da transação.
        state (TxState): Estado corrente no ciclo de vida de 2PC.
        payload (dict[str, Any]): Conteúdo de dados da operação associada.
        details (str | None, opcional): Mensagens auxiliares, erros ou justificativas de abort.
    """
    tx_id: str
    state: TxState
    payload: dict[str, Any]
    details: str | None = None


class TwoPhaseParticipant:
    """Representa um nó participante em um protocolo Two-Phase Commit.

    Armazena o estado das transações locais e responde aos comandos de PREPARE,
    COMMIT e ABORT emitidos pelo coordenador.
    """

    def __init__(self, node_id: str) -> None:
        """Inicializa o participante com seu identificador de nó.

        Args:
            node_id (str): Identificador único deste participante.
        """
        self.node_id = str(node_id)
        self.transactions: dict[str, TxRecord] = {}
        self._lock = asyncio.Lock()

    async def prepare(
        self,
        tx_id: str,
        payload: dict[str, Any],
        validator: Callable[[dict[str, Any]], bool] | None = None,
    ) -> bool:
        """Executa a Fase 1 (Prepare): valida a transação e trava recursos necessários.

        Args:
            tx_id (str): Identificador da transação.
            payload (dict[str, Any]): Dados da transação a serem preparados.
            validator (Callable, opcional): Função síncrona/validador de regras de negócio locais.

        Returns:
            bool: True se o participante vota YES (PREPARED), False se vota NO (ABORTED).
        """
        async with self._lock:
            if validator and not validator(payload):
                self.transactions[tx_id] = TxRecord(
                    tx_id=tx_id,
                    state=TxState.ABORTED,
                    payload=payload,
                    details="validator rejected",
                )
                return False

            self.transactions[tx_id] = TxRecord(tx_id=tx_id, state=TxState.PREPARED, payload=payload)
            return True

    async def commit(self, tx_id: str) -> bool:
        """Executa a Fase 2 (Commit): efetiva a transação previamente preparada.

        Args:
            tx_id (str): Identificador da transação.

        Returns:
            bool: True se o commit foi realizado com sucesso a partir do estado PREPARED, False caso contrário.
        """
        async with self._lock:
            record = self.transactions.get(tx_id)
            if not record or record.state != TxState.PREPARED:
                return False
            record.state = TxState.COMMITTED
            return True

    async def abort(self, tx_id: str) -> bool:
        """Executa a Fase 2 (Abort): cancela e desfaz a transação preparada ou pendente.

        Args:
            tx_id (str): Identificador da transação.

        Returns:
            bool: Sempre True indicando que a transação foi abortada/limpa localmente.
        """
        async with self._lock:
            record = self.transactions.get(tx_id)
            if record:
                record.state = TxState.ABORTED
            else:
                self.transactions[tx_id] = TxRecord(tx_id=tx_id, state=TxState.ABORTED, payload={})
            return True


class TwoPhaseCoordinator:
    """Orquestrador do protocolo Two-Phase Commit responsável pela coordenação global.

    Gerencia o envio das fases de PREPARE, coleta das votações e posterior
    disparo da decisão atômica (COMMIT ou ABORT) para todos os participantes.
    """

    def __init__(
        self,
        coordinator_id: str,
        participants: list[str],
        prepare_call: Callable[[str, str, dict[str, Any]], Awaitable[bool]],
        commit_call: Callable[[str, str], Awaitable[bool]],
        abort_call: Callable[[str, str], Awaitable[bool]],
    ) -> None:
        """Inicializa o coordenador com os canais de comunicação com os participantes.

        Args:
            coordinator_id (str): Identificador do nó coordenador.
            participants (list[str]): Lista de identificadores dos nós participantes.
            prepare_call (Callable): Função assíncrona (participant, tx_id, payload) -> bool.
            commit_call (Callable): Função assíncrona (participant, tx_id) -> bool.
            abort_call (Callable): Função assíncrona (participant, tx_id) -> bool.
        """
        self.coordinator_id = str(coordinator_id)
        self.participants = list(participants)
        self.prepare_call = prepare_call
        self.commit_call = commit_call
        self.abort_call = abort_call

        self.transactions: dict[str, TxRecord] = {}
        self._lock = asyncio.Lock()

    async def execute_transaction(
        self,
        tx_id: str,
        payload: dict[str, Any],
        timeout_seconds: float = 4.0,
    ) -> bool:
        """Coordena o ciclo completo da transação distribuída com semântica de tudo-ou-nada.

        Dispara PREPARE em paralelo para todos os participantes. Se todos responderem YES
        dentro do timeout, decide COMMIT e envia confirmação; caso contrário, decide ABORT.

        Args:
            tx_id (str): Identificador único da transação.
            payload (dict[str, Any]): Carga de dados da transação.
            timeout_seconds (float, opcional): Tempo máximo para recebimento dos votos na fase Prepare.

        Returns:
            bool: True se a transação obteve consenso unânime e foi comitada, False se foi abortada.
        """
        async with self._lock:
            self.transactions[tx_id] = TxRecord(tx_id=tx_id, state=TxState.PREPARING, payload=payload)

        prepare_tasks = [
            asyncio.create_task(self._safe_prepare(participant, tx_id, payload))
            for participant in self.participants
        ]

        try:
            results = await asyncio.wait_for(asyncio.gather(*prepare_tasks), timeout=timeout_seconds)
            all_yes = all(results) and len(results) == len(self.participants)
        except asyncio.TimeoutError:
            all_yes = False

        decision = TxState.COMMITTED if all_yes else TxState.ABORTED

        async with self._lock:
            self.transactions[tx_id].state = decision

        if decision == TxState.COMMITTED:
            commit_tasks = [
                asyncio.create_task(self._safe_commit(p, tx_id))
                for p in self.participants
            ]
            await asyncio.gather(*commit_tasks)
            return True
        else:
            abort_tasks = [
                asyncio.create_task(self._safe_abort(p, tx_id))
                for p in self.participants
            ]
            await asyncio.gather(*abort_tasks)
            return False

    async def _safe_prepare(self, participant: str, tx_id: str, payload: dict[str, Any]) -> bool:
        """Executa a chamada assíncrona de prepare tratando exceções como voto negativo (NO)."""
        try:
            return await self.prepare_call(participant, tx_id, payload)
        except Exception:
            return False

    async def _safe_commit(self, participant: str, tx_id: str) -> bool:
        """Executa a chamada assíncrona de commit com tolerância defensiva a erros transitórios."""
        try:
            return await self.commit_call(participant, tx_id)
        except Exception:
            return False

    async def _safe_abort(self, participant: str, tx_id: str) -> bool:
        """Executa a chamada assíncrona de abort garantindo que o comando seja emitido."""
        try:
            return await self.abort_call(participant, tx_id)
        except Exception:
            return False
