import asyncio
import os
import subprocess
from collections.abc import Mapping
from typing import Any

from cursor_sdk import (
    AgentOptions,
    CursorAgentError,
    CustomTool,
    CustomToolContext,
    LocalAgentOptions,
    RunResult,
)
from cursor_sdk.asyncio import AsyncAgent, AsyncClient

from app.config import BASE_DIR, get_cursor_api_key
from app.exceptions.error_messages import (
    CURSOR_API_KEY_MISSING_MESSAGE,
    FAILURE_ANALYSIS_INCOMPLETE_MESSAGE,
    FAILURE_ANALYSIS_START_ERROR_MESSAGE,
    FAILURE_ANALYSIS_UNAVAILABLE_MESSAGE,
    LOG_EMPTY_ERROR_MESSAGE,
    MAINTENANCE_ANALYSIS_UNAVAILABLE_MESSAGE,
)
from app.services.steam_catalog import describe_route

# Modelo usado nas análises. O SDK exige um modelo na execução local.
ANALYSIS_MODEL: str = "composer-2.5"


class FailureAnalysisError(RuntimeError):
    """Erro ao consultar o Cursor Agent.

    Serve para separar duas situações. ValueError indica que o log
    recebido é inválido. FailureAnalysisError indica que o log era
    válido, mas a análise não pôde ser concluída.
    """


def analyze_failure(log: str, diff: str | None = None) -> str:
    """Envia a falha da pipeline ao Cursor Agent e devolve a análise.

    O agente recebe o log e, quando existir, o diff das alterações.
    A chamada pede apenas uma resposta em texto. Ela não aplica a
    correção no projeto.

    Parâmetros:
        log: texto da falha capturado na execução dos testes.
        diff: diferença do código associada à falha. É opcional.

    Retorno:
        Texto final produzido pelo agente, sem espaços nas pontas.

    Erros:
        ValueError: o log está vazio ou contém somente espaços.
        FailureAnalysisError: a chave de acesso não está definida,
        o agente não chegou a iniciar ou a execução não terminou.
    """
    # Um log vazio não tem conteúdo para analisar. A verificação
    # acontece antes de ler a chave e antes de contactar o Cursor.
    if not log.strip():
        raise ValueError(LOG_EMPTY_ERROR_MESSAGE)

    # A chave é lida do ambiente. config.py já carregou o .env local
    # para esse ambiente. O valor não fica escrito no código.
    api_key = get_cursor_api_key()
    if not api_key:
        raise FailureAnalysisError(CURSOR_API_KEY_MISSING_MESSAGE)

    try:
        result = _execute_analysis(_build_prompt(log, diff), _agent_options(api_key))
    except CursorAgentError as error:
        # Esse erro ocorre antes de existir uma análise. Os casos
        # comuns são chave recusada, falha de rede ou configuração
        # inválida. "from error" guarda a causa original.
        raise FailureAnalysisError(
            f"{FAILURE_ANALYSIS_START_ERROR_MESSAGE} {error.message}"
        ) from error

    # "finished" é o status de uma análise concluída. "error" significa
    # que a execução começou e falhou no meio. Uma resposta em branco
    # também não serve como diagnóstico.
    if result.status != "finished" or not result.result.strip():
        details = (result.error_message or "").strip()
        message = FAILURE_ANALYSIS_INCOMPLETE_MESSAGE
        if details:
            message = f"{message} {details}"
        raise FailureAnalysisError(message)

    return result.result.strip()


def explain_maintenance_warning(warning: str) -> str:
    """Pede ao agente uma explicação para um aviso de manutenção.

    O log junta o aviso e os últimos commits. Se a chave, o Git ou o
    agente falharem, devolve um texto curto em vez de interromper a
    pipeline.
    """
    log: str = f"{warning.strip()}\n\nCommits recentes:\n{_recent_commits()}"
    try:
        return analyze_failure(log)
    except (FailureAnalysisError, ValueError, OSError) as error:
        return f"{MAINTENANCE_ANALYSIS_UNAVAILABLE_MESSAGE} {error}"


def explain_pipeline_failure(log: str) -> str:
    """Pede ao agente uma análise para uma falha da pipeline.

    O log junta a falha e os últimos commits. Se a chave, o Git ou o
    agente falharem, devolve um texto curto. Quem chamou decide se a
    falha original continua depois da análise.
    """
    full_log: str = f"{log.strip()}\n\nCommits recentes:\n{_recent_commits()}"
    try:
        return analyze_failure(full_log)
    except (FailureAnalysisError, ValueError, OSError) as error:
        return f"{FAILURE_ANALYSIS_UNAVAILABLE_MESSAGE} {error}"


def _recent_commits() -> str:
    """Lê os cinco commits mais recentes sem deixar o agente executar o Git."""
    try:
        completed: subprocess.CompletedProcess[str] = subprocess.run(
            ["git", "log", "-5", "--oneline"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "Os commits recentes não puderam ser lidos."

    if completed.returncode != 0:
        return "Os commits recentes não puderam ser lidos."

    output: str = completed.stdout.strip()
    return output or "Não há commits recentes."


def _agent_options(api_key: str) -> AgentOptions:
    """Monta a configuração enviada ao agente.

    tools vazio impede o uso de ferramentas. O agente só pode responder
    com texto e não altera arquivos nem executa comandos. A execução
    local usa a pasta em que o processo está.
    """
    return AgentOptions(
        api_key=api_key,
        model=ANALYSIS_MODEL,
        # Sem ferramentas internas, o agente não edita arquivos nem executa
        # comandos. A única ferramenta é a consulta ao catálogo da Steam.
        tools=[],
        local=LocalAgentOptions(
            cwd=os.getcwd(),
            custom_tools={
                "consultar_rota_steam": CustomTool(
                    description=(
                        "Consulta o catálogo da Steam e informa se a rota "
                        "pedida está desatualizada, qual é a versão mais alta "
                        "e o que mudou nos parâmetros."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "interface": {"type": "string"},
                            "method": {"type": "string"},
                            "version": {"type": "integer"},
                        },
                        "required": ["interface", "method", "version"],
                    },
                    execute=_consultar_rota_steam,
                )
            },
        ),
    )


def _consultar_rota_steam(
    args: Mapping[str, Any],
    context: CustomToolContext,
) -> str:
    """Ferramenta do agente para conferir uma rota no catálogo da Steam."""
    del context
    interface: object = args.get("interface")
    method: object = args.get("method")
    version: object = args.get("version")
    if not isinstance(interface, str) or not isinstance(method, str):
        return "Informe interface e method para consultar a rota da Steam."
    if isinstance(version, bool) or not isinstance(version, int):
        return "Informe a version numérica da rota da Steam."
    return describe_route(interface, method, version)


def _execute_analysis(prompt: str, options: AgentOptions) -> RunResult:
    """Inicia a análise e espera o resultado.

    O cliente síncrono do SDK falha no Windows ao abrir o processo
    auxiliar: o Python tenta observar um pipe com uma função que, nesse
    sistema, só aceita soquetes. O cliente assíncrono abre o mesmo
    processo por outro caminho e funciona no Windows e no Linux.
    asyncio.run permite que analyze_failure continue sendo síncrona.
    """
    return asyncio.run(_request_analysis(prompt, options))


async def _request_analysis(prompt: str, options: AgentOptions) -> RunResult:
    """Abre o agente, envia uma mensagem e encerra a sessão.

    AsyncAgent.prompt cria o agente, envia o texto e espera o fim da
    execução. O contexto async with fecha a conexão ao terminar.
    """
    async with await AsyncClient.launch_bridge(workspace=os.getcwd()) as client:
        return await AsyncAgent.prompt(prompt, options, client=client)


def _build_prompt(log: str, diff: str | None) -> str:
    """Monta a mensagem enviada ao agente.

    O traço inicial no nome indica que a função é de uso interno deste
    módulo. Quem chama a análise usa analyze_failure.

    A mensagem pede cinco tópicos. São os mesmos que depois poderão
    aparecer no comentário do Pull Request: descrição, causa, trecho
    do log, sugestão e riscos. Também deixa explícito que o agente
    não deve alterar o projeto.

    O diff só entra na mensagem quando traz algum conteúdo. Espaços
    sozinhos são tratados como ausência de diff.
    """
    sections = [
        "Você analisa uma falha de pipeline CI/CD para um desenvolvedor.",
        "Não altere arquivos, não execute comandos e não aplique correções.",
        "Se o log falar de uma rota da Steam desatualizada, use a ferramenta",
        "consultar_rota_steam com interface, method e version.",
        "Informe a rota obsoleta, a rota atual e a diferença dos parâmetros.",
        "Se o log incluir commits recentes, use-os para explicar o que",
        "pode ter acontecido, o que pode ser feito e os riscos.",
        "Responda em português, com estes tópicos:",
        "- Descrição da falha",
        "- Possível causa raiz",
        "- Trecho relevante do log",
        "- Sugestão de correção",
        "- Possíveis riscos ou efeitos colaterais",
        "",
        "Log da falha:",
        log.strip(),
    ]

    if diff is not None and diff.strip():
        sections.extend(["", "Diff das alterações:", diff.strip()])

    # Cada item da lista vira uma linha da mensagem.
    return "\n".join(sections)
