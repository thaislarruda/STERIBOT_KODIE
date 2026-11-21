
import os
import json

from pathlib import Path
from dotenv import load_dotenv

from google import genai
from google.genai import types
from openai import OpenAI


# ==========================================
# 1. CONFIGURAÇÕES GERAIS
# ==========================================

ROOT_DIR = Path(__file__).resolve().parents[3]

load_dotenv(ROOT_DIR / ".env")

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()

PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "prompts"
    / "steribot.txt"
)


# ==========================================
# 2. CONFIGURAÇÃO DOS PROVEDORES
# ==========================================

def configurar_gemini():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não encontrada no arquivo .env."
        )

    return genai.Client(api_key=api_key)


def configurar_openai():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY não encontrada no arquivo .env."
        )

    return OpenAI(api_key=api_key)


# ==========================================
# 3. CARREGAMENTO DO PROMPT
# ==========================================

def carregar_prompt():
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"Prompt não encontrado: {PROMPT_PATH}"
        )

    return PROMPT_PATH.read_text(encoding="utf-8")


# ==========================================
# 4. ORGANIZAÇÃO DO HISTÓRICO
# ==========================================

def formatar_historico(historico):
    if not historico:
        return "Não há mensagens anteriores nesta sessão."

    mensagens = []

    for item in historico:
        papel = item.get("papel", "usuário")
        conteudo = item.get("conteudo", "")

        mensagens.append(
            f"{papel.upper()}: {conteudo}"
        )

    return "\n".join(mensagens)


# ==========================================
# 5. VALIDAÇÃO DA RESPOSTA
# ==========================================

def validar_resposta(conteudo: str) -> dict:
    if not conteudo:
        raise RuntimeError(
            "O modelo de IA não retornou conteúdo."
        )

    try:
        resultado = json.loads(conteudo)

    except json.JSONDecodeError as erro:
        raise RuntimeError(
            "O modelo retornou uma resposta que não é JSON válido."
        ) from erro

    if not isinstance(resultado, dict):
        raise RuntimeError(
            "A resposta da IA precisa ser um objeto JSON."
        )

    campos_obrigatorios = [
        "resposta",
        "categoria",
        "equipamento",
        "problema",
        "prioridade",
        "nivel_atendimento",
        "status",
        "proxima_acao",
        "informacoes_pendentes",
        "necessita_atendimento_humano"
    ]

    campos_ausentes = [
        campo
        for campo in campos_obrigatorios
        if campo not in resultado
    ]

    if campos_ausentes:
        raise RuntimeError(
            f"Resposta incompleta. Campos ausentes: {campos_ausentes}"
        )

    return resultado


# ==========================================
# 6. COMUNICAÇÃO COM GEMINI
# ==========================================

def gerar_resposta_gemini(
    mensagem: str,
    prompt: str,
    historico: str
) -> dict:

    client = configurar_gemini()

    model = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.8-flash"
    )

    conteudo = f"""
    HISTÓRICO DA CONVERSA:

    {historico}

    MENSAGEM ATUAL DO USUÁRIO:

    {mensagem}

    Considere o histórico para dar continuidade ao atendimento.
    Não repita perguntas que já foram respondidas.
    Mantenha as informações já identificadas.
    Se houver informações conflitantes, peça esclarecimento.

    Responda obrigatoriamente em JSON válido,
    seguindo todas as instruções do STERIBOT.
    """

    response = client.models.generate_content(
        model=model,
        contents=conteudo,
        config=types.GenerateContentConfig(
            system_instruction=prompt,
            response_mime_type="application/json",
            temperature=0.2
        )
    )

    return validar_resposta(response.text)


# ==========================================
# 7. COMUNICAÇÃO COM OPENAI
# ==========================================

def gerar_resposta_openai(
    mensagem: str,
    prompt: str,
    historico: str
) -> dict:

    client = configurar_openai()

    model = os.getenv(
        "OPENAI_MODEL",
        "gpt-6-luna"
    )

    conteudo = f"""
    HISTÓRICO DA CONVERSA:

    {historico}

    MENSAGEM ATUAL DO USUÁRIO:

    {mensagem}

    Considere o histórico para dar continuidade ao atendimento.
    Não repita perguntas que já foram respondidas.
    Mantenha as informações já identificadas.
    Se houver informações conflitantes, peça esclarecimento.

    Responda obrigatoriamente em formato JSON válido,
    seguindo todas as instruções do STERIBOT.
    """

    response = client.responses.create(
        model=model,
        instructions=prompt,
        input=conteudo,
        text={
            "format": {
                "type": "json_object"
            }
        }
    )

    return validar_resposta(response.output_text)


# ==========================================
# 8. SERVIÇO PRINCIPAL DE IA
# ==========================================

def gerar_resposta(
    mensagem: str,
    historico: list | None = None
) -> dict:

    if not mensagem or not mensagem.strip():
        raise ValueError(
            "A mensagem não pode estar vazia."
        )

    prompt = carregar_prompt()

    historico_formatado = formatar_historico(
        historico
    )

    if AI_PROVIDER == "gemini":

        return gerar_resposta_gemini(
            mensagem=mensagem,
            prompt=prompt,
            historico=historico_formatado
        )

    elif AI_PROVIDER == "openai":

        return gerar_resposta_openai(
            mensagem=mensagem,
            prompt=prompt,
            historico=historico_formatado
        )

    else:
        raise ValueError(
            f"Provedor de IA não reconhecido: {AI_PROVIDER}. "
            "Utilize 'gemini' ou 'openai'."
        )
