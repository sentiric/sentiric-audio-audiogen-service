import os

class Settings:
    APP_NAME = "Sentiric AudioGen SFX Engine"
    APP_VERSION = "1.0.0"
    ENV = os.getenv("ENV", "production")
    DEVICE = os.getenv("AUDIO_SERVICE_DEVICE", "cuda")
    # Meta AudioGen Medium modeli (SFX için en iyisi)
    MODEL_ID = os.getenv("AUDIOGEN_MODEL_ID", "facebook/audiogen-medium")
    
    HTTP_PORT = int(os.getenv("AUDIOGEN_SERVICE_HTTP_PORT", "16320"))
    GRPC_PORT = int(os.getenv("AUDIOGEN_SERVICE_GRPC_PORT", "16321"))
    METRICS_PORT = int(os.getenv("AUDIOGEN_SERVICE_METRICS_PORT", "16322"))

    # mTLS
    GRPC_TLS_CA_PATH = os.getenv("GRPC_TLS_CA_PATH", "/sentiric-certificates/certs/ca.crt")
    CERT_PATH = os.getenv("AUDIOGEN_SERVICE_CERT_PATH", "/sentiric-certificates/certs/audio-audiogen-service-chain.crt")
    KEY_PATH = os.getenv("AUDIOGEN_SERVICE_KEY_PATH", "/sentiric-certificates/certs/audio-audiogen-service.key")

    # Storage & MQ
    S3_ENDPOINT = os.getenv("BUCKET_ENDPOINT_URL", "http://minio:9000")
    S3_ACCESS_KEY = os.getenv("BUCKET_ACCESS_KEY_ID", "sentiric")
    S3_SECRET_KEY = os.getenv("BUCKET_SECRET_ACCESS_KEY", "sentiric-secret-key")
    S3_BUCKET = os.getenv("BUCKET_NAME", "sentiric")
    RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://sentiric:sentiric_pass@rabbitmq:5672/%2f")

settings = Settings()