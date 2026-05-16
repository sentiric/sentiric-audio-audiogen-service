# [ARCH-COMPLIANCE] SOP-01: Eksiksiz Teslimat
import torch, uuid, os, boto3, asyncio, structlog, aio_pika, scipy.io.wavfile
from transformers import AutoProcessor, AudioGenForConditionalGeneration
from botocore.config import Config
from app.core.config import settings
from sentiric.event.v1 import event_pb2
from google.protobuf.timestamp_pb2 import Timestamp

logger = structlog.get_logger()

class AudioGenEngine:
    def __init__(self):
        self.processor = None
        self.model = None
        self.s3 = boto3.client(
            's3', 
            endpoint_url=settings.S3_ENDPOINT, 
            aws_access_key_id=settings.S3_ACCESS_KEY, 
            aws_secret_access_key=settings.S3_SECRET_KEY, 
            config=Config(signature_version='s3v4')
        )

    def initialize(self):
        logger.info(f"Loading {settings.MODEL_ID}", event_id="MODEL_INIT")
        try:
            self.processor = AutoProcessor.from_pretrained(settings.MODEL_ID)
            self.model = AudioGenForConditionalGeneration.from_pretrained(settings.MODEL_ID).to(settings.DEVICE)
            logger.info("AudioGen Ready.", event_id="MODEL_READY")
        except Exception as e:
            logger.error(f"Load Fail: {e}", event_id="MODEL_INIT_FAIL")

    async def generate_async(self, prompt: str, duration: int, job_id: str, trace_id: str, tenant_id: str):
        logger.info("Generating SFX...", event_id="SFX_GEN_START", trace_id=trace_id)
        path = f"/tmp/{job_id}.wav"
        
        def render():
            inputs = self.processor(text=[prompt], padding=True, return_tensors="pt").to(settings.DEVICE)
            # AudioGen tokens (approx 50 per sec)
            tokens = min(duration * 50, 500) 
            audio_values = self.model.generate(**inputs, max_new_tokens=tokens)
            sampling_rate = self.model.config.audio_encoder.sampling_rate
            scipy.io.wavfile.write(path, rate=sampling_rate, data=audio_values[0, 0].cpu().numpy())
            
        def clear_vram():
            if settings.DEVICE == "cuda": 
                torch.cuda.empty_cache()
            
        try:
            # 1. Render Audio
            await asyncio.to_thread(render)
            
            # 2. Upload S3
            object_name = f"sfx/{job_id}.wav"
            await asyncio.to_thread(self.s3.upload_file, path, settings.S3_BUCKET, object_name)
            os.remove(path)
            
            s3_uri = f"s3://{settings.S3_BUCKET}/{object_name}"
            logger.info("SFX uploaded", event_id="SFX_GEN_SUCCESS", trace_id=trace_id, uri=s3_uri)
            
            # 3. Publish Success Event
            await self._publish_event(
                routing_key="media.generation.completed",
                event_type="media.generation.completed",
                trace_id=trace_id, job_id=job_id, tenant_id=tenant_id,
                success=True, result_uri=s3_uri, error_message=""
            )
                
        except Exception as e:
            err_msg = str(e)
            logger.error(f"SFX Render failed: {err_msg}", event_id="SFX_GEN_FAIL", trace_id=trace_id)
            if os.path.exists(path):
                os.remove(path)
                
            # [ARCH-COMPLIANCE FIX] 4. Publish Failed Event
            await self._publish_event(
                routing_key="media.generation.failed",
                event_type="media.generation.failed",
                trace_id=trace_id, job_id=job_id, tenant_id=tenant_id,
                success=False, result_uri="", error_message=err_msg
            )
        finally:
            # VRAM Temizliği thread bloklamasın
            await asyncio.to_thread(clear_vram)

    async def _publish_event(self, routing_key: str, event_type: str, trace_id: str, job_id: str, tenant_id: str, success: bool, result_uri: str, error_message: str):
        try:
            conn = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            async with conn:
                ch = await conn.channel()
                ex = await ch.declare_exchange("sentiric_events", aio_pika.ExchangeType.TOPIC, durable=True)
                ts = Timestamp(); ts.GetCurrentTime()
                
                evt = event_pb2.MediaGenerationCompletedEvent(
                    event_type=event_type, 
                    trace_id=trace_id, job_id=job_id, tenant_id=tenant_id, 
                    media_type="sfx", success=success, result_uri=result_uri, 
                    error_message=error_message, timestamp=ts
                )
                
                await ex.publish(
                    aio_pika.Message(body=evt.SerializeToString(), content_type="application/protobuf"), 
                    routing_key=routing_key
                )
        except Exception as e:
            logger.error(f"Failed to publish event to RMQ: {e}", event_id="RMQ_PUBLISH_FAIL", trace_id=trace_id)

audiogen_engine = AudioGenEngine()