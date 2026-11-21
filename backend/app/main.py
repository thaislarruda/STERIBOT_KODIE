
import os
import json
import logging

from uuid import uuid4
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app.services.ia_service import gerar_resposta


# ==========================================
# 1. CONFIGURAÇÕES GERAIS
# ==========================================

ROOT_DIR = Path(__file__).resolve().parents[2]

load_dotenv(ROOT_DIR / ".env")

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()

TEMPO_LIMITE_N8N = 5

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("steribot")


app = FastAPI(
    title="STERIBOT API",
    description="API de atendimento e suporte técnico da STERIFAST",
    version="0.4.0"
)


# ==========================================
# 2. CONFIGURAÇÃO CORS
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# 3. ARMAZENAMENTO TEMPORÁRIO DAS SESSÕES
# ==========================================

SESSOES = {}

LIMITE_HISTORICO = 12


# ==========================================
# 4. MODELO DE ENTRADA
# ==========================================

class Atendimento(BaseModel):
    mensagem: str
    equipamento: str | None = None
    sessao_id: str | None = None


# ==========================================
# 5. INTEGRAÇÃO COM N8N
# ==========================================

def enviar_para_n8n(
    resultado: dict,
    sessao_id: str
) -> bool:
    """
    Envia os dados estruturados do atendimento
    para o Webhook do n8n.

    Uma falha no n8n não interrompe a resposta
    do STERIBOT ao usuário.
    """

    if not N8N_WEBHOOK_URL:
        logger.warning(
            "N8N_WEBHOOK_URL não configurada. "
            "Atendimento não enviado ao n8n."
        )
        return False

    dados = {
        "sessao_id": sessao_id,
        "resposta": resultado.get("resposta", ""),
        "categoria": resultado.get("categoria", ""),
        "equipamento": resultado.get("equipamento", ""),
        "problema": resultado.get("problema", ""),
        "prioridade": resultado.get("prioridade", ""),
        "nivel_atendimento": resultado.get("nivel_atendimento", ""),
        "status": resultado.get("status", ""),
        "proxima_acao": resultado.get("proxima_acao", ""),
        "necessita_atendimento_humano": resultado.get(
            "necessita_atendimento_humano",
            False
        )
    }

    corpo = json.dumps(
        dados,
        ensure_ascii=False
    ).encode("utf-8")

    requisicao = Request(
        N8N_WEBHOOK_URL,
        data=corpo,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )

    try:
        with urlopen(
            requisicao,
            timeout=TEMPO_LIMITE_N8N
        ) as resposta:

            codigo = resposta.status

            if 200 <= codigo < 300:
                logger.info(
                    "Atendimento enviado ao n8n. "
                    "Sessão: %s | HTTP: %s",
                    sessao_id,
                    codigo
                )
                return True

            logger.warning(
                "n8n retornou HTTP %s para a sessão %s.",
                codigo,
                sessao_id
            )

            return False

    except HTTPError as erro:
        logger.error(
            "Erro HTTP ao enviar atendimento ao n8n: %s",
            erro.code
        )
        return False

    except URLError as erro:
        logger.error(
            "Não foi possível conectar ao n8n: %s",
            erro.reason
        )
        return False

    except Exception:
        logger.exception(
            "Erro inesperado na integração com o n8n."
        )
        return False


# ==========================================
# 6. ROTAS INICIAIS
# ==========================================

@app.get("/")
def inicio():
    return {
        "projeto": "STERIBOT",
        "mensagem": "Assistente de suporte técnico STERIFAST",
        "status": "API funcionando"
    }


@app.get("/health")
def verificar_saude():
    return {
        "status": "online",
        "servico": "STERIBOT API",
        "sessoes_ativas": len(SESSOES),
        "integracao_n8n_configurada": bool(N8N_WEBHOOK_URL)
    }


# ==========================================
# 7. RECEBER E CONTINUAR ATENDIMENTO
# ==========================================

@app.post("/atendimento")
def receber_atendimento(dados: Atendimento):

    if not dados.mensagem.strip():
        raise HTTPException(
            status_code=400,
            detail="A mensagem não pode estar vazia."
        )

    sessao_id = dados.sessao_id or str(uuid4())

    historico = SESSOES.get(sessao_id, [])

    try:

        # Gera a resposta do STERIBOT
        resultado = gerar_resposta(
            mensagem=dados.mensagem,
            historico=historico
        )

        # Atualiza o histórico da conversa
        historico.append({
            "papel": "usuário",
            "conteudo": dados.mensagem
        })

        historico.append({
            "papel": "steribot",
            "conteudo": resultado["resposta"]
        })

        historico = historico[-LIMITE_HISTORICO:]

        SESSOES[sessao_id] = historico

        # Inclui o identificador da sessão
        resultado["sessao_id"] = sessao_id

        # Envia os dados estruturados ao n8n
        registro_enviado = enviar_para_n8n(
            resultado=resultado,
            sessao_id=sessao_id
        )

        # Informa o resultado da integração
        resultado["registro_n8n"] = (
            "enviado" if registro_enviado else "pendente"
        )

        # Retorna a resposta ao frontend
        return resultado

    except Exception as erro:

        logger.exception(
            "Erro ao processar atendimento."
        )

        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar atendimento: {str(erro)}"
        )


# ==========================================
# 8. CONSULTAR HISTÓRICO
# ==========================================

@app.get("/atendimento/{sessao_id}/historico")
def consultar_historico(sessao_id: str):

    if sessao_id not in SESSOES:
        raise HTTPException(
            status_code=404,
            detail="Sessão não encontrada."
        )

    return {
        "sessao_id": sessao_id,
        "historico": SESSOES[sessao_id]
    }


# ==========================================
# 9. ENCERRAR SESSÃO
# ==========================================

@app.delete("/atendimento/{sessao_id}")
def encerrar_atendimento(sessao_id: str):

    if sessao_id not in SESSOES:
        raise HTTPException(
            status_code=404,
            detail="Sessão não encontrada."
        )

    del SESSOES[sessao_id]

    return {
        "status": "encerrada",
        "sessao_id": sessao_id,
        "mensagem": "Histórico da sessão removido."
    }
