# [ARCH-COMPLIANCE] SOP-01: Eksiksiz Teslimat
import torch, uuid, os, boto3, asyncio, structlog, aio_pika, scipy.io.wavfile
import numpy as np
from botocore.config import Config
from app.core.config import settings
from sentiric.event.v1 import event_pb2
from google.protobuf.timestamp_pb2 import Timestamp

# [FINAL BOSS FIX]: Hugging Face Lazy-Loading mekanizmasını BYPASS ediyoruz.
# Sınıfları fiziksel olarak bulundukları alt modüllerden zorla çekiyoruz.
try:
    # 1. Hugging Face içindeki AudioGen model sınıfı (Underscore'lu yol)
    from transformers.models.audio_gen.modeling_audio_gen import AudioGenForConditionalGeneration
    # 2. İşlemci sınıfı
    from transformers.models.audio_gen.processing_audio_gen import AudioGenProcessor as AutoProcessor
    
    logger_init = structlog.get_logger()
    logger_init.info("AudioGen classes force-loaded via absolute path", event_id="IMPORT_SUCCESS")
except Exception as e:
    # Bu aşamada hata gelirse requirements.txt'de transformersMain veya encodec eksiktir.
    raise ImportError(f"FATAL: AudioGen internal paths changed or dependencies missing: {e}")

logger = structlog.get_logger()

class AudioGenEngine:
    def __init__(self):
        self.processor = None
        self.model = None
        self.s3 = boto3.client('s3', 
            endpoint_url=settings.S3_ENDPOINT, 
            aws_access_key_id=settings.S3_ACCESS_KEY, 
            aws_secret_access_key=settings.S3_SECRET_KEY, 
            config=Config(signature_version='s3v4')
        )

    def initialize(self):
        logger.info(f"Initializing SFX Engine: {settings.MODEL_ID}", event_id="MODEL_INIT")
        try:
            # Model yüklenirken VRAM optimizasyonu
            self.processor = AutoProcessor.from_pretrained(settings.MODEL_ID)
            self.model = AudioGenForConditionalGeneration.from_pretrained(
                settings.MODEL_ID, 
                torch_dtype=torch.float16 if settings.DEVICE == "cuda" else torch.float32
            ).to(settings.DEVICE)
            
            self.model.eval()
            logger.info("AudioGen Ready (Force-Loaded).", event_id="MODEL_READY")
        except Exception as e:
            logger.error(f"Load Fail: {e}", event_id="MODEL_INIT_FAIL")

    async def generate_async(self, prompt: str, duration: int, job_id: str, trace_id: str, tenant_id: str):
        logger.info(f"Generating SFX for: {prompt}", event_id="SFX_GEN_START", trace_id=trace_id)
        path = f"/tmp/{job_id}.wav"
        
        def render():
            inputs = self.processor(text=[prompt], padding=True, return_tensors="pt").to(settings.DEVICE)
            # AudioGen: ~50 token = 1 saniye (Max 10sn sınırı)
            tokens = min(duration * 50, 500) 
            
            with torch.inference_mode():
                audio_values = self.model.generate(**inputs, max_new_tokens=tokens)
            
            sampling_rate = self.model.config.audio_encoder.sampling_rate
            audio_data = audio_values[0, 0].cpu().numpy()
            scipy.io.wavfile.write(path, rate=sampling_rate, data=audio_data)
            
        try:
            await asyncio.to_thread(render)
            
            object_name = f"sfx/{job_id}.wav"
            await asyncio.to_thread(self.s3.upload_file, path, settings.S3_BUCKET, object_name)
            if os.path.exists(path): os.remove(path)
            
            s3_uri = f"s3://{settings.S3_BUCKET}/{object_name}"
            logger.info("SFX uploaded", event_id="SFX_GEN_SUCCESS", trace_id=trace_id, uri=s3_uri)
            await self._publish_event("media.generation.completed", trace_id, job_id, tenant_id, True, s3_uri)
                
        except Exception as e:
            err_msg = str(e)
            logger.error(f"SFX Render failed: {err_msg}", event_id="SFX_GEN_FAIL", trace_id=trace_id)
            if os.path.exists(path): os.remove(path)
            await self._publish_event("media.generation.failed", trace_id, job_id, tenant_id, False, "", err_msg)
        finally:
            if settings.DEVICE == "cuda": torch.cuda.empty_cache()

    async def _publish_event(self, event_type, trace_id, job_id, tenant_id, success, uri, err=""):
        try:
            conn = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            async with conn:
                ch = await conn.channel()
                ex = await ch.declare_exchange("sentiric_events", aio_pika.ExchangeType.TOPIC, durable=True)
                ts = Timestamp(); ts.GetCurrentTime()
                evt = event_pb2.MediaGenerationCompletedEvent(
                    event_type=event_type, trace_id=trace_id, job_id=job_id, tenant_id=tenant_id, 
                    media_type="sfx", success=success, result_uri=uri, error_message=err, timestamp=ts
                )
                await ex.publish(
                    aio_pika.Message(body=evt.SerializeToString(), content_type="application/protobuf"), 
                    routing_key=event_type
                )
        except Exception as e:
            logger.error(f"RMQ Publish Fail: {e}")

audiogen_engine = AudioGenEngine()