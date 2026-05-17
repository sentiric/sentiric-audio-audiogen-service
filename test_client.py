# test_client.py
import grpc
import os
from sentiric.audio_gen.v1 import gateway_pb2, gateway_pb2_grpc

def run_test():
    # mTLS Sertifikalarınızın doğru dizini
    base_cert_dir = "../sentiric-certificates/certs"
    
    ca_path = os.path.join(base_cert_dir, "ca.crt")
    client_cert_path = os.path.join(base_cert_dir, "audio-audiogen-service-chain.crt")
    client_key_path = os.path.join(base_cert_dir, "audio-audiogen-service.key")

    try:
        with open(ca_path, "rb") as f: ca_cert = f.read()
        with open(client_cert_path, "rb") as f: client_cert = f.read()
        with open(client_key_path, "rb") as f: client_key = f.read()
    except FileNotFoundError:
        print(f"❌ Sertifikalar bulunamadı! {base_cert_dir} dizinini kontrol edin.")
        return

    credentials = grpc.ssl_channel_credentials(ca_cert, client_key, client_cert)
    
    print("📡 mTLS Kanalı açılıyor (localhost:16321)...")
    with grpc.secure_channel("localhost:16321", credentials) as channel:
        stub = gateway_pb2_grpc.AudioGatewayServiceStub(channel)
        
        request = gateway_pb2.SubmitAudioJobRequest(
            tenant_id="tenant-local-dev-1",
            trace_id="test-trace-123",
            prompt="A cinematic distant explosion with rumbling debris, high quality",
            audio_type="sfx",
            duration_seconds=3
        )
        
        print(f"🎵 Job Gönderiliyor: '{request.prompt}'")
        try:
            response = stub.SubmitAudioJob(request)
            print(f"✅ Job Kabul Edildi: {response.accepted}")
            print(f"🆔 Job ID: {response.job_id}")
        except grpc.RpcError as e:
            print(f"❌ gRPC Hatası: {e.code()} - {e.details()}")

if __name__ == "__main__":
    run_test()