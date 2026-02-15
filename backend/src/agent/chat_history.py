"""
Chat History Manager: Memória conversacional persistente no Postgres.
Armazena mensagens em formato OpenAI para replay exato no agente.
"""
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from loguru import logger
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse


DROP_QS_KEYS = {"pgbouncer", "connection_limit"}


def _sanitize_dsn(database_url: str) -> str:
    u = urlparse(database_url)
    qs = dict(parse_qsl(u.query, keep_blank_values=True))
    for k in list(qs.keys()):
        if k in DROP_QS_KEYS:
            qs.pop(k, None)
    new_query = urlencode(qs, doseq=True)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))


class ChatHistoryManager:
    """Gerencia histórico de chat no Postgres."""

    def __init__(self):
        db_url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
        if db_url:
            self.db_url = _sanitize_dsn(db_url)
        else:
            self.db_url = None
            logger.warning("Sem DATABASE_URL - historico desabilitado")

    def _get_connection(self):
        if not self.db_url:
            return None
        return psycopg2.connect(self.db_url, sslmode="require")

    def load_history(self, telefone: str, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Carrega últimas N mensagens em formato OpenAI.
        Reconstrói tool_calls e tool responses no formato correto.
        """
        conn = self._get_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT role, content, tool_calls, tool_call_id, name
                FROM chat_history
                WHERE telefone = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (telefone, limit),
            )
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            # Reverter ordem (DESC -> cronológica)
            rows.reverse()

            messages = []
            for row in rows:
                msg = {"role": row["role"]}

                if row["role"] == "assistant" and row["tool_calls"]:
                    # Mensagem de assistant com tool_calls
                    if row["content"]:
                        msg["content"] = row["content"]
                    else:
                        msg["content"] = None
                    msg["tool_calls"] = row["tool_calls"]
                elif row["role"] == "tool":
                    # Resposta de tool
                    msg["content"] = row["content"] or ""
                    msg["tool_call_id"] = row["tool_call_id"] or ""
                    if row["name"]:
                        msg["name"] = row["name"]
                else:
                    # user ou assistant normal
                    msg["content"] = row["content"] or ""

                messages.append(msg)

            # Sanitizar: garantir que toda msg 'tool' tenha um 'assistant' com tool_calls antes
            messages = self._sanitize_messages(messages)

            return messages

        except Exception as e:
            logger.error(f"Erro ao carregar historico: {e}")
            if conn:
                conn.close()
            return []

    @staticmethod
    def _sanitize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sanitiza mensagens para garantir formato valido para a OpenAI API.

        Regras:
        - Toda mensagem role='tool' DEVE ser precedida por um assistant com tool_calls
        - Se uma tool msg esta orfa (sem assistant+tool_calls antes), remove ela
        - Se um assistant com tool_calls nao tem tool responses depois, remove ele
        """
        if not messages:
            return messages

        # Coletar IDs de tool_calls existentes nos assistants
        valid_tool_call_ids = set()
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tc_id = tc.get("id", "")
                    if tc_id:
                        valid_tool_call_ids.add(tc_id)

        # Primeira passada: remover tool messages orfas
        cleaned = []
        for msg in messages:
            if msg.get("role") == "tool":
                tool_call_id = msg.get("tool_call_id", "")
                if tool_call_id in valid_tool_call_ids:
                    cleaned.append(msg)
                else:
                    logger.warning(
                        f"Removendo tool msg orfa (tool_call_id={tool_call_id})"
                    )
            else:
                cleaned.append(msg)

        # Segunda passada: verificar que assistant+tool_calls tem tool responses
        # Coletar IDs de tool responses presentes
        present_tool_ids = set()
        for msg in cleaned:
            if msg.get("role") == "tool":
                present_tool_ids.add(msg.get("tool_call_id", ""))

        final = []
        for msg in cleaned:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                # Verificar se TODAS as tool_calls tem responses
                all_ids = [tc.get("id", "") for tc in msg["tool_calls"]]
                if all(tid in present_tool_ids for tid in all_ids):
                    final.append(msg)
                else:
                    # Converter para assistant simples (sem tool_calls)
                    logger.warning(
                        f"Removendo tool_calls orfos de assistant msg"
                    )
                    if msg.get("content"):
                        final.append({"role": "assistant", "content": msg["content"]})
                    # Se nao tem content, simplesmente remove
            else:
                final.append(msg)

        if len(final) != len(messages):
            logger.info(
                f"Historico sanitizado: {len(messages)} -> {len(final)} mensagens"
            )

        return final

    def save_message(
        self,
        telefone: str,
        role: str,
        content: Optional[str] = None,
        tool_calls: Optional[List[Dict]] = None,
        tool_call_id: Optional[str] = None,
        name: Optional[str] = None,
        media_type: str = "text",
        media_url: Optional[str] = None,
    ):
        """Salva uma mensagem no histórico."""
        conn = self._get_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_history
                    (telefone, role, content, tool_calls, tool_call_id, name, media_type, media_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    telefone,
                    role,
                    content,
                    json.dumps(tool_calls) if tool_calls else None,
                    tool_call_id,
                    name,
                    media_type,
                    media_url,
                ),
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao salvar mensagem: {e}")
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except Exception:
                    pass

    def get_last_message_time(self, telefone: str) -> Optional[datetime]:
        """Retorna timestamp da última mensagem (para detecção de nova conversa)."""
        conn = self._get_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT created_at
                FROM chat_history
                WHERE telefone = %s AND role = 'user'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (telefone,),
            )
            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if row:
                return row[0]
            return None

        except Exception as e:
            logger.error(f"Erro ao buscar ultima mensagem: {e}")
            if conn:
                conn.close()
            return None

    def is_new_conversation(self, telefone: str, timeout_minutes: int = 30) -> bool:
        """Verifica se é uma nova conversa (>timeout_minutes sem mensagens)."""
        last_time = self.get_last_message_time(telefone)
        if not last_time:
            return True

        now = datetime.now(timezone.utc)
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)

        delta = (now - last_time).total_seconds()
        return delta > (timeout_minutes * 60)
