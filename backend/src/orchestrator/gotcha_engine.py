"""
GOTCHA Engine - Orquestrador Principal
Goals → Orchestration → Tools
Context → Hardprompts → Args
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class GOTCHAEngine:
    """Orquestrador que executa Goals usando Tools"""

    def __init__(self, base_path: Optional[str] = None):
        """
        Inicializa o GOTCHA Engine.

        Args:
            base_path: Caminho base do projeto (opcional)
        """
        if base_path is None:
            # Detectar automaticamente (3 níveis acima: orchestrator/ → src/ → backend/ → raiz)
            current_file = Path(__file__)
            base_path = current_file.parent.parent.parent.parent

        self.base_path = Path(base_path)
        logger.info(f"🎯 GOTCHA Engine inicializado: {self.base_path}")

        # Carregar componentes
        self.context = self._load_context()
        self.args = self._load_args()
        self.goals = self._load_goals()

        logger.info("✅ GOTCHA Engine pronto!")

    def _load_context(self) -> Dict[str, Any]:
        """Carrega contexto de negócio (YAML files)"""
        context = {}

        try:
            context_path = self.base_path / "context"

            # Produtos em destaque
            produtos_file = context_path / "produtos_destaque.yaml"
            if produtos_file.exists():
                with open(produtos_file, 'r', encoding='utf-8') as f:
                    context['produtos'] = yaml.safe_load(f)

            # Frases de atendimento
            frases_file = context_path / "frases_atendimento.yaml"
            if frases_file.exists():
                with open(frases_file, 'r', encoding='utf-8') as f:
                    context['frases'] = yaml.safe_load(f)

            # Políticas da loja
            politicas_file = context_path / "politicas_loja.yaml"
            if politicas_file.exists():
                with open(politicas_file, 'r', encoding='utf-8') as f:
                    context['politicas'] = yaml.safe_load(f)

            logger.info(f"📚 Context carregado: {len(context)} arquivos")

        except Exception as e:
            logger.error(f"❌ Erro ao carregar context: {e}")
            context = {}

        return context

    def _load_args(self) -> Dict[str, Any]:
        """Carrega configurações (args)"""
        args = {}

        try:
            args_path = self.base_path / "args"

            # Comportamento do agente
            comportamento_file = args_path / "comportamento_agente.yaml"
            if comportamento_file.exists():
                with open(comportamento_file, 'r', encoding='utf-8') as f:
                    args['comportamento'] = yaml.safe_load(f)

            # Limites operacionais
            limites_file = args_path / "limites_operacionais.yaml"
            if limites_file.exists():
                with open(limites_file, 'r', encoding='utf-8') as f:
                    args['limites'] = yaml.safe_load(f)

            logger.info(f"⚙️ Args carregados: {len(args)} arquivos")

        except Exception as e:
            logger.error(f"❌ Erro ao carregar args: {e}")
            args = {}

        return args

    def _load_goals(self) -> Dict[str, str]:
        """Carrega goals disponíveis (apenas paths por enquanto)"""
        goals = {}

        try:
            goals_path = self.base_path / "goals"

            if goals_path.exists():
                for goal_file in goals_path.glob("*.md"):
                    if goal_file.name != "README.md":
                        goal_name = goal_file.stem  # Nome sem extensão
                        goals[goal_name] = str(goal_file)

            logger.info(f"🎯 Goals encontrados: {len(goals)}")

        except Exception as e:
            logger.error(f"❌ Erro ao carregar goals: {e}")
            goals = {}

        return goals

    def get_template(
        self,
        template_name: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Carrega e formata template de hardprompts.

        Args:
            template_name: Nome do template (ex: "saudacao")
            variables: Variáveis para substituir {key}

        Returns:
            Template formatado

        Example:
            >>> template = engine.get_template("saudacao", {
            ...     "nome": "João",
            ...     "saudacao": "Bom dia"
            ... })
        """
        try:
            template_path = self.base_path / "hardprompts" / f"{template_name}.txt"

            if not template_path.exists():
                logger.warning(f"⚠️ Template não encontrado: {template_name}")
                return ""

            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()

            # Substituir variáveis
            if variables:
                for key, value in variables.items():
                    placeholder = f"{{{key}}}"
                    template = template.replace(placeholder, str(value))

            return template

        except Exception as e:
            logger.error(f"❌ Erro ao carregar template {template_name}: {e}")
            return ""

    def get_config(self, path: str, default: Any = None) -> Any:
        """
        Acessa configuração usando dot notation.

        Args:
            path: Caminho da config (ex: "comportamento.personalidade.tom")
            default: Valor padrão se não encontrado

        Returns:
            Valor da configuração

        Example:
            >>> tom = engine.get_config("comportamento.personalidade.tom", "amigavel")
        """
        try:
            keys = path.split(".")
            value = self.args

            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default

            return value

        except Exception as e:
            logger.error(f"❌ Erro ao acessar config {path}: {e}")
            return default

    def get_context(self, path: str, default: Any = None) -> Any:
        """
        Acessa contexto usando dot notation.

        Args:
            path: Caminho do contexto (ex: "frases.saudacoes.manha")
            default: Valor padrão se não encontrado

        Returns:
            Valor do contexto

        Example:
            >>> saudacoes = engine.get_context("frases.saudacoes.manha", [])
        """
        try:
            keys = path.split(".")
            value = self.context

            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default

            return value

        except Exception as e:
            logger.error(f"❌ Erro ao acessar context {path}: {e}")
            return default

    def format_saudacao(
        self,
        nome: Optional[str] = None,
        horario: str = "manha",
        cliente_conhecido: bool = False,
        historico: Optional[str] = None
    ) -> str:
        """
        Formata saudação personalizada usando context + templates.

        Args:
            nome: Nome do cliente
            horario: "manha", "tarde", "noite"
            cliente_conhecido: Se cliente é conhecido
            historico: Menção ao histórico (opcional)

        Returns:
            Saudação formatada

        Example:
            >>> saudacao = engine.format_saudacao("João", "manha", True)
        """
        # Pegar saudação do context
        saudacoes = self.get_context(f"frases.saudacoes.{horario}", [])
        saudacao = saudacoes[0] if saudacoes else "Olá!"

        # Emoji baseado no horário
        emoji_map = {
            "manha": "☀️",
            "tarde": "🌤️",
            "noite": "🌙"
        }
        emoji = emoji_map.get(horario, "😊")

        # Apresentação
        if cliente_conhecido:
            apresentacao = ""
        else:
            apresentacao = self.get_context(
                "frases.apresentacao.informal",
                "Bem-vindo à Roça Capital! 😊"
            )

        # Contexto histórico
        contexto_historico = ""
        if cliente_conhecido and historico:
            contexto_historico = f"\n\nVi que você {historico}."

        # Montar saudação
        nome_str = f" {nome}" if nome else ""
        mensagem = f"{saudacao}{nome_str}! {emoji}"

        if apresentacao:
            mensagem += f"\n\n{apresentacao}"

        if contexto_historico:
            mensagem += contexto_historico

        mensagem += "\n\nComo posso ajudar você hoje?"

        return mensagem

    def should_bot_respond(self) -> bool:
        """
        Verifica se bot deve responder (baseado em configurações).

        Returns:
            True se bot deve responder
        """
        sempre_ativo = self.get_config(
            "comportamento.horario_atendimento.sempre_ativo",
            True
        )

        return sempre_ativo

    def get_max_produtos_busca(self) -> int:
        """Retorna limite máximo de produtos na busca"""
        return self.get_config("comportamento.limites.max_produtos_busca", 10)

    def get_max_itens_carrinho(self) -> int:
        """Retorna limite máximo de itens no carrinho"""
        return self.get_config("limites.negocio.carrinho.max_itens", 20)

    def __repr__(self) -> str:
        return f"<GOTCHAEngine goals={len(self.goals)} context={len(self.context)} args={len(self.args)}>"


# Singleton global (opcional)
_gotcha_instance: Optional[GOTCHAEngine] = None


def get_gotcha_engine() -> GOTCHAEngine:
    """
    Retorna instância singleton do GOTCHA Engine.

    Returns:
        GOTCHAEngine instance
    """
    global _gotcha_instance

    if _gotcha_instance is None:
        _gotcha_instance = GOTCHAEngine()

    return _gotcha_instance


# Para testes
if __name__ == "__main__":
    # Testar engine
    engine = GOTCHAEngine()

    print(f"\n{engine}\n")

    # Testar template
    print("📝 Teste de Template:")
    saudacao = engine.format_saudacao("João", "manha", True, "comprou queijo conosco em janeiro")
    print(saudacao)
    print()

    # Testar configs
    print("⚙️ Teste de Configs:")
    print(f"Tom: {engine.get_config('comportamento.personalidade.tom')}")
    print(f"Max produtos busca: {engine.get_max_produtos_busca()}")
    print(f"Max itens carrinho: {engine.get_max_itens_carrinho()}")
    print()

    # Testar context
    print("📚 Teste de Context:")
    print(f"Saudações manhã: {engine.get_context('frases.saudacoes.manha')}")
    print()

    print("✅ GOTCHA Engine funcionando!")
