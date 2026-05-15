import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.logging_utils import setup_logging
from app.core.engine import audiogen_engine
from app.grpc_server import serve_grpc

# LTX veya Image servisinden kopyaladığın setup_logging'i kullanabilirsin
from app.core.logging_utils import setup_logging
setup_logging("audio-audiogen-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    audiogen_engine.initialize()
    task = asyncio.create_task(serve_grpc())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/healthz")
def health(): return {"status": "ok", "service": "audio-audiogen-service"}