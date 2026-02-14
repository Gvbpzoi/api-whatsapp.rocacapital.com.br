"""
AI Agent: Loop principal do agente conversacional usando OpenAI Function Calling.
Substitui intent_classifier + intent_handlers + response_evaluator + gotcha_engine.
"""
import json
import os
from typing import Optional
from loguru import logger
from openai import AsyncOpenAI

from .system_prompt import build_system_prompt
from .tool_definitions import get_tool_definitions
from .tool_executor import ToolExecutor
from .chat_history import ChatHistoryManager


class AIAgent:
    """
    Agente conversacional usando OpenAI Function Calling.

    O agente:
    1. Carrega histórico do Postgres
    2. Envia system prompt + histórico + mensagem para GPT-4.1-mini
    3. Se o modelo retorna tool_calls, executa e faz loop
    4. Retorna a resposta final de texto
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY nao configurada")
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.tool_executor = ToolExecutor()
        self.tools = get_tool_definitions()
        self.history_manager = ChatHistoryManager()
        self.max_iterations = 10

        logger.info(f"AI Agent inicializado com modelo {self.model}")

    async def process_message(
        self,
        telefone: str,
        user_message: str,
        media_type: str = "text",
        media_url: Optional[str] = None,
    ) -> str:
        """
        Processa uma mensagem do usuário e retorna a resposta do agente.

        Args:
            telefone: Telefone do cliente
            user_message: Mensagem de texto (ou transcrição/descrição para mídia)
            media_type: 'text', 'audio', 'image', 'document'
            media_url: URL do arquivo de mídia (se aplicável)

        Returns:
            Resposta final do agente
        """
        try:
            # 1. Montar system prompt com telefone
            system_prompt = build_system_prompt(telefone)

            # 2. Carregar últimas 30 mensagens do Postgres
            history = self.history_manager.load_history(telefone, limit=30)

            # 3. Salvar mensagem do usuário no histórico
            self.history_manager.save_message(
                telefone=telefone,
                role="user",
                content=user_message,
                media_type=media_type,
                media_url=media_url,
            )

            # 4. Montar array de mensagens
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})

            # 5. Loop do agente (chama modelo, executa tools, repete)
            for iteration in range(self.max_iterations):
                logger.debug(f"Agent iteration {iteration + 1} para {telefone[:8]}")

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto",
                    temperature=0.7,
                    max_tokens=1500,
                )

                assistant_message = response.choices[0].message

                # Se não tem tool_calls, temos a resposta final
                if not assistant_message.tool_calls:
                    final_text = assistant_message.content or ""

                    # Salvar resposta no histórico
                    self.history_manager.save_message(
                        telefone=telefone,
                        role="assistant",
                        content=final_text,
                    )

                    logger.info(
                        f"Agent respondeu em {iteration + 1} iteracao(es) para {telefone[:8]}"
                    )
                    return final_text

                # Processar tool calls
                # Adicionar mensagem do assistant (com tool_calls) ao array
                assistant_dict = {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in assistant_message.tool_calls
                    ],
                }
                messages.append(assistant_dict)

                # Salvar mensagem de tool_calls no histórico
                self.history_manager.save_message(
                    telefone=telefone,
                    role="assistant",
                    content=assistant_message.content,
                    tool_calls=assistant_dict["tool_calls"],
                )

                # Executar cada tool call
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                    logger.info(f"Tool call: {function_name}({json.dumps(arguments, ensure_ascii=False)[:200]})")

                    result = await self.tool_executor.execute(
                        function_name, arguments, telefone
                    )

                    tool_message = {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                    messages.append(tool_message)

                    # Salvar resultado da tool no histórico
                    self.history_manager.save_message(
                        telefone=telefone,
                        role="tool",
                        content=result,
                        tool_call_id=tool_call.id,
                        name=function_name,
                    )

            # Se atingiu max iterações
            logger.warning(f"Agent atingiu max iteracoes para {telefone[:8]}")
            return "Desculpe, tive um problema ao processar. Pode tentar novamente?"

        except Exception as e:
            logger.error(f"Erro no agent para {telefone[:8]}: {e}")
            return "Ops, tive um problema tecnico. Pode tentar novamente em alguns segundos?"
