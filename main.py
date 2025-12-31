import os
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi_limiter import FastAPILimiter
from dotenv import load_dotenv
from app.utils.lock import file_lock

from app.routers import (
    estoque, avaliacoes_vuca, ficha_tecnica, produtosdevenda, auditoria, totalrecebidodelivery, percentplp,
    tempomedio99food, tempomedioifood, tempomediocozinha, plp, avaliacoes_ifood, relatorios_99food
)   
from app.utils.responses import erro_resposta
from app.utils.logger_config import configurar_logger


#--------------- CONFIG BÁSICAS ---------------
load_dotenv()
REDIS_URL = os.getenv("REDIS_URL")

logger = configurar_logger()

#--------------- APP com LIFESPAN ---------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Executa automaticamente quando a API inicia e quando encerra.
    Aqui inicializamos e fechamos a conexão com o Redis.
    """    
    redis_conn = None
    if not REDIS_URL:
        logger.warning("⚠️  REDIS_URL não definido — o rate limit ficará desativado.")
    else:
        try:
            redis_conn = redis.from_url(REDIS_URL, encoding="utf8", decode_responses=True)
            await FastAPILimiter.init(redis_conn)
            logger.info("✅ Conectado ao Redis e Rate Limiter inicializado.")
        except Exception as e:
            logger.error(f"Erro ao conectar no Redis: {e}")
            logger.warning("Rate limiting desativado.")
            
    yield
    
    if redis_conn:
        await redis_conn.close()
        logger.info("🔌 Conexão com Redis encerrada com sucesso.")
        
#--------------- INICIALIZAÇÃO DO FASTAPI ---------------
app = FastAPI(
    title="Api de Relatórios Automatizados",
    description="Automação para download de relatórios CSV via SeleniunBase",
    version="3.0.0",
    lifespan=lifespan
)
  
#--------------- HANDLERS DE ERROS PADRÃO ---------------
@app.exception_handler(RequestValidationError)
async def validation_exception_hander(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content=erro_resposta("Parâmetros invalidos."))

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: Exception):
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(status_code=exc.status_code, content=erro_resposta(str(detail)))

@app.exception_handler(Exception)
async def enhandled_exception_hander(request: Request, exc: Exception):
    logger.exception("Erro não tratado:", exc_info=True)
    return JSONResponse(status_code=500, content=erro_resposta("Erro interno no servidor"))

#--------------- REGISTRO DOS ROUTERS ---------------
app.include_router(estoque.router)
app.include_router(auditoria.router)
app.include_router(avaliacoes_vuca.router)
app.include_router(avaliacoes_ifood.router)
app.include_router(ficha_tecnica.router)
app.include_router(produtosdevenda.router)
app.include_router(tempomedio99food.router)
app.include_router(tempomedioifood.router)
app.include_router(tempomediocozinha.router)
app.include_router(relatorios_99food.router)
app.include_router(totalrecebidodelivery.router)
app.include_router(percentplp.router)
app.include_router(plp.router)

#--------------- ENDPOINT DE STATUS ---------------
@app.get("/status", tags=["Sistema"])
def status():
    return {"status": "ok", "redis": bool(REDIS_URL)}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/debug-erro")
def ver_print_erro():
    caminho_imagem = "ERRO_TELA_BOTAO.png" # O mesmo nome que definimos na automação
    
    if os.path.exists(caminho_imagem):
        return FileResponse(caminho_imagem)
    else:
        return {"mensagem": "Nenhum print de erro encontrado no momento."}
