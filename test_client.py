# test_client.py
import grpc
import os
import sys
import argparse
import time
import uuid
import random
from sentiric.audio_gen.v1 import gateway_pb2, gateway_pb2_grpc

# --- 🎵 PROFESYONEL AUDIOGEN YETENEK KATALOĞU ---
# Not: Her sesin doğasına uygun 'ideal saniyeler' (d) belirlenmiştir.
EXAMPLES = {
    "cinematic": [
        {"p": "Deep cinematic sub-bass impact with a long metallic tail, high fidelity", "d": 6},
        {"p": "Epic orchestral brass swell leading into a massive drum hit, reverb", "d": 8},
        {"p": "Fast cinematic transition swoosh, digital glitch texture, 4k audio", "d": 3},
        {"p": "Slow atmospheric drone with shimmering high-end textures", "d": 10}
    ],
    "nature": [
        {"p": "Violent thunderstorm with loud cracking lightning and heavy rain on metal roof", "d": 10},
        {"p": "Calm forest morning, light wind, various birds singing at different distances", "d": 10},
        {"p": "Gentle ocean waves lapping against small pebbles on a quiet beach", "d": 10},
        {"p": "Vicious wind howling through a frozen pine forest during winter", "d": 8}
    ],
    "horror": [
        {"p": "Creepy metal scraping in a dark abandoned hospital corridor, long reverb", "d": 7},
        {"p": "Deep demonic growl echoing in a limestone cave, menacing", "d": 5},
        {"p": "Ghostly whispers and cold wind blowing through an old dusty attic", "d": 8},
        {"p": "Distant muffled screams behind a heavy wooden door, scratching sounds", "d": 6}
    ],
    "sci-fi": [
        {"p": "Spaceship interior hum with various digital computer beeps and telemetry", "d": 8},
        {"p": "Laser gun charging up with rising pitch followed by a powerful discharge", "d": 5},
        {"p": "Teleportation effect, shimmering energy sound with a low frequency pulse", "d": 4},
        {"p": "Alien planet atmosphere with strange liquid bubbling and whistling wind", "d": 10}
    ],
    "foley": [
        {"p": "Old rusty key turning in a heavy iron lock and door creaking open", "d": 4},
        {"p": "Crispy potato chips bag opening and hands rummaging inside", "d": 4},
        {"p": "A glass bottle shattering on a concrete floor, shards sliding", "d": 3},
        {"p": "Pouring hot coffee into a ceramic mug, steam and bubbling sounds", "d": 5}
    ]
}

def send_job(stub, prompt, duration, tenant_id):
    """Tek bir AudioGen işini gRPC üzerinden gönderir."""
    trace_id = str(uuid.uuid4())
    request = gateway_pb2.SubmitAudioJobRequest(
        tenant_id=tenant_id,
        trace_id=trace_id,
        prompt=prompt,
        audio_type="sfx",
        duration_seconds=duration
    )
    
    print(f"📡 [TRACE: {trace_id[:8]}] Gönderiliyor: '{prompt[:60]}...' | Süre: {duration}s")
    try:
        start_time = time.time()
        response = stub.SubmitAudioJob(request)
        elapsed = time.time() - start_time
        
        if response.accepted:
            print(f"  ✅ KABUL EDİLDİ | Job ID: {response.job_id} | İletim: {elapsed:.2f}s")
        else:
            print(f"  ❌ REDDEDİLDİ")
    except grpc.RpcError as e:
        print(f"  🚨 gRPC HATASI: {e.code()} - {e.details()}")

def run_test():
    parser = argparse.ArgumentParser(description="Sentiric AudioGen Professional Test Suite")
    parser.add_argument("--prompt", type=str, help="Özel bir ses açıklaması yazın")
    parser.add_argument("--duration", type=int, help="Ses süresi (Belirtilmezse kataloğu kullanır)")
    parser.add_argument("--category", type=str, choices=list(EXAMPLES.keys()) + ["all"], help="Kategorideki tüm sesleri test et")
    parser.add_argument("--stress", type=int, default=1, help="Her işi kaç kez üst üste göndersin? (Concurrency testi)")
    parser.add_argument("--tenant", type=str, default="tenant-local-dev", help="Tenant ID")
    
    args = parser.parse_args()

    # --- mTLS SERTİFİKA YAPILANDIRMASI ---
    base_cert_dir = "../sentiric-certificates/certs"
    try:
        with open(os.path.join(base_cert_dir, "ca.crt"), "rb") as f: ca_cert = f.read()
        with open(os.path.join(base_cert_dir, "audio-audiogen-service-chain.crt"), "rb") as f: client_cert = f.read()
        with open(os.path.join(base_cert_dir, "audio-audiogen-service.key"), "rb") as f: client_key = f.read()
    except FileNotFoundError:
        print(f"❌ KRİTİK HATA: Sertifikalar '{base_cert_dir}' dizininde bulunamadı!")
        return

    creds = grpc.ssl_channel_credentials(ca_cert, client_key, client_cert)
    
    print("🚀 Sentiric AudioGen Test Operasyonu Başlatılıyor...")
    print("-" * 70)

    with grpc.secure_channel("localhost:16321", creds) as channel:
        stub = gateway_pb2_grpc.AudioGatewayServiceStub(channel)
        
        # SENARYO 1: Kullanıcı özel prompt girdi
        if args.prompt:
            dur = args.duration if args.duration else 5
            for _ in range(args.stress):
                send_job(stub, args.prompt, dur, args.tenant)
            
        # SENARYO 2: Kategori testi (Toplu gönderim)
        elif args.category:
            target_cats = EXAMPLES.keys() if args.category == "all" else [args.category]
            for cat in target_cats:
                print(f"\n📂 KATEGORİ: {cat.upper()}")
                for item in EXAMPLES[cat]:
                    dur = args.duration if args.duration else item["d"]
                    for _ in range(args.stress):
                        send_job(stub, item["p"], dur, args.tenant)
                        # Semaphore'u ve asenkron yapıyı test etmek için bekleme eklemiyoruz
                    
        # SENARYO 3: Parametresiz çalışma (Rastgele bir örnek seç)
        else:
            cat_name = random.choice(list(EXAMPLES.keys()))
            item = random.choice(EXAMPLES[cat_name])
            dur = args.duration if args.duration else item["d"]
            print(f"🎲 Rastgele Seçilen Kategori: {cat_name.upper()}")
            send_job(stub, item["p"], dur, args.tenant)

    print("-" * 70)
    print("🏁 İşlemler tamamlandı. Servis loglarını takip ederek üretimi izleyin.")

if __name__ == "__main__":
    run_test()


# ### 🛠️

# 1.  **Dinamik Süre Yönetimi:** `EXAMPLES` içindeki her sesin kendine has bir süresi var (Örn: Cam kırılması 3s, Fırtına 10s). Eğer komut satırından `--duration` vermezsen, model en kaliteli sesi vereceği saniyede çalışır.
# 2.  **Gelişmiş Veri Yapısı:** `EXAMPLES` artık bir liste değil, `p` (prompt) ve `d` (duration) içeren bir sözlükler kümesi.
# 3.  **Hız Ölçümü:** İşin gRPC üzerinden kabul edilme hızını (latency) saniye cinsinden gösterir.
# 4.  **Stress Test Modu:** `--stress 5` dersen, her sesi arka arkaya 5 kez gönderir. Bu, yazdığımız **Semaphore** mekanizmasını test etmek için en iyi yoldur.
# 5.  **Görselleştirme:** Çıktılar artık daha okunaklı, kategoriler ve trace ID'ler net bir şekilde ayrılmış durumda.

# ### 🚀 Örnek Kullanım Senaryoları

# *   **Tüm Sinematik sesleri ideal sürelerinde sırayla üret:**
#     ```bash
#     python test_client.py --category cinematic
#     ```

# *   **Servise yüklen (Stress Test):** (Semaphore'un 1'er 1'er işlediğini loglardan izle)
#     ```bash
#     python test_client.py --category sci-fi --stress 3
#     ```

# *   **Tüm dünyayı (Bütün kategorileri) tek komutla oluştur:**
#     ```bash
#     python test_client.py --category all
#     ```

# *   **Hızlı bir rastgele deneme yap:**
#     ```bash
#     python test_client.py
#     ```
