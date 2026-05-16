# test_client.py
import grpc
from sentiric.audio_gen.v1 import gateway_pb2, gateway_pb2_grpc

def run_test():
    # mTLS Sertifikalarınızı yükleyin
    with open("ca.crt", "rb") as f: ca_cert = f.read()
    with open("client.crt", "rb") as f: client_cert = f.read()
    with open("client.key", "rb") as f: client_key = f.read()

    credentials = grpc.ssl_channel_credentials(ca_cert, client_key, client_cert)
    
    with grpc.secure_channel("localhost:16321", credentials) as channel:
        stub = gateway_pb2_grpc.AudioGatewayServiceStub(channel)
        
        request = gateway_pb2.SubmitAudioJobRequest(
            tenant_id="tenant-local-dev-1",
            trace_id="test-trace-123",
            prompt="Dog barking in the distance, high quality",
            audio_type="sfx",
            duration_seconds=3
        )
        
        print(f"📡 Sending Job Request to AudioGen...")
        response = stub.SubmitAudioJob(request)
        print(f"✅ Job Accepted: {response.accepted}")
        print(f"🆔 Job ID: {response.job_id}")
        print(f"⏳ Now check the console of the server and your S3 bucket / RabbitMQ!")

if __name__ == "__main__":
    run_test()