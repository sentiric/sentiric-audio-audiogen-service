# [ARCH-COMPLIANCE] SOP-01: Eksiksiz Teslimat
import torch, uuid, os, boto3, asyncio, structlog, aio_pika, scipy.io.wavfile
import numpy as np
from botocore.config import Config
from app.core.config import settings
from sentiric.event.v1 import event_pb2
from google.protobuf.timestamp_pb2 import Timestamp

# [CRITICAL] Meta Audiocraft Import
try:
    from audiocraft.models import AudioGen
    from audiocraft.data.audio import audio_write
except ImportError as e:
    raise ImportError(f"FATAL: audiocraft not found. Error: {e}")

logger = structlog.get_logger()

class AudioGenEngine:
    def __init__(self):
        self.model = None
        self.s3 = boto3.client('s3', 
            endpoint_url=settings.S3_ENDPOINT, 
            aws_access_key_id=settings.S3_ACCESS_KEY, 
            aws_secret_access_key=settings.S3_SECRET_KEY, 
            config=Config(signature_version='s3v4')
        )

    def initialize(self):
        logger.info(f"Loading AudioGen: {settings.MODEL_ID}", event_id="MODEL_INIT")
        try:
            # Meta Audiocraft yöntemiyle model yükleme
            self.model = AudioGen.get_pretrained(settings.MODEL_ID, device=settings.DEVICE)
            logger.info("AudioGen Ready (via Audiocraft).", event_id="MODEL_READY")
        except Exception as e:
            logger.error(f"Load Fail: {e}", event_id="MODEL_INIT_FAIL")

    async def generate_async(self, prompt: str, duration: int, job_id: str, trace_id: str, tenant_id: str):
        logger.info(f"Generating SFX: {prompt}", event_id="SFX_GEN_START", trace_id=trace_id)
        path = f"/tmp/{job_id}" # audiocraft kendi .wav ekler
        
        def render():
            # Parametreleri set et
            self.model.set_generation_params(duration=min(duration, 10))
            
            with torch.inference_mode():
                # Üretim (list of prompts döner)
                wav = self.model.generate([prompt])
            
            # audiocraft'ın kendi save metodu (loudness normalizasyonu ile)
            audio_write(
                path, 
                wav[0].cpu(), 
                self.model.sample_rate, 
                strategy="loudness", 
                loudness_compressor=True
            )
            
        try:
            await asyncio.to_thread(render)
            
            final_wav_path = f"{path}.wav"
            object_name = f"sfx/{job_id}.wav"
            
            await asyncio.to_thread(self.s3.upload_file, final_wav_path, settings.S3_BUCKET, object_name)
            if os.path.exists(final_wav_path): os.remove(final_wav_path)
            
            s3_uri = f"s3://{settings.S3_BUCKET}/{object_name}"
            logger.info("SFX uploaded", event_id="SFX_GEN_SUCCESS", trace_id=trace_id, uri=s3_uri)
            await self._publish_event("media.generation.completed", trace_id, job_id, tenant_id, True, s3_uri)
                
        except Exception as e:
            err_msg = str(e)
            logger.error(f"SFX Render failed: {err_msg}", event_id="SFX_GEN_FAIL", trace_id=trace_id)
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
                await ex.publish(aio_pika.Message(body=evt.SerializeToString()), routing_key=event_type)
        except Exception as e:
            logger.error(f"RMQ Fail: {e}")

audiogen_engine = AudioGenEngine()