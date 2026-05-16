# [ARCH-COMPLIANCE] SOP-01: Eksiksiz Teslimat
import grpc, asyncio, uuid, structlog
from concurrent import futures
from sentiric.audio_gen.v1 import gateway_pb2, gateway_pb2_grpc
from app.core.engine import audiogen_engine
from app.core.config import settings

logger = structlog.get_logger()

class AudioGatewayServicer(gateway_pb2_grpc.AudioGatewayServiceServicer):
    async def SubmitAudioJob(self, request, context):
        metadata = dict(context.invocation_metadata())
        
        # [ARCH-COMPLIANCE FIX] Önce Protobuf payload'a bak, yoksa Metadata'dan (SUTS/Tracing) al.
        trace_id = getattr(request, "trace_id", "") or metadata.get("x-trace-id", "unknown")
        tenant_id = getattr(request, "tenant_id", "") or metadata.get("x-tenant-id", "unknown")
        job_id = str(uuid.uuid4())

        logger.info(f"AudioGen Job Accepted: {request.prompt}", event_id="GRPC_JOB_ACCEPTED", trace_id=trace_id)
        
        # Arka planda üretimi başlat (CQRS: Hemen Job_ID dön, işi arkada yap)
        asyncio.create_task(
            audiogen_engine.generate_async(
                prompt=request.prompt, 
                duration=request.duration_seconds, 
                job_id=job_id, 
                trace_id=trace_id, 
                tenant_id=tenant_id
            )
        )

        return gateway_pb2.SubmitAudioJobResponse(accepted=True, job_id=job_id)

async def serve_grpc():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=2))
    gateway_pb2_grpc.add_AudioGatewayServiceServicer_to_server(AudioGatewayServicer(), server)
    
    listen_addr = f"[::]:{settings.GRPC_PORT}"
    try:
        with open(settings.KEY_PATH, "rb") as f: pk = f.read()
        with open(settings.CERT_PATH, "rb") as f: cert = f.read()
        with open(settings.GRPC_TLS_CA_PATH, "rb") as f: ca = f.read()
        creds = grpc.ssl_server_credentials([(pk, cert)], root_certificates=ca, require_client_auth=True)
        server.add_secure_port(listen_addr, creds)
        logger.info(f"gRPC mTLS Ready on {listen_addr}", event_id="GRPC_SERVER_START")
    except Exception as e:
        logger.error(f"mTLS Fail: {e}", event_id="MTLS_FAIL")
        raise e
        
    await server.start()
    await server.wait_for_termination()