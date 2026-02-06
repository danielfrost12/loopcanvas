"""
═══════════════════════════════════════════════════════════════
  LoopCanvas GPU Worker — Google Colab Edition
═══════════════════════════════════════════════════════════════

  Open this file in Google Colab (Runtime → Change runtime type → GPU)
  and run all cells. The worker will:

  1. Install dependencies
  2. Clone the LoopCanvas repo
  3. Connect to the job queue
  4. Generate canvases at FULL quality (SDXL + SVD on T4 GPU)
  5. Upload results back to the server
  6. Loop until the session ends or queue is empty

  Cost: $0 (Colab free tier gives you a T4 GPU for ~4-12 hours)

  To use this:
  1. Go to colab.research.google.com
  2. File → Upload notebook (or paste this as a .py)
  3. Runtime → Change runtime type → GPU (T4)
  4. Run all cells
  5. The worker handles everything from there

═══════════════════════════════════════════════════════════════
"""

# ══════════════════════════════════════════════════
# CELL 1: Install dependencies
# ══════════════════════════════════════════════════

# !pip install -q torch torchvision diffusers transformers accelerate
# !pip install -q pillow librosa numpy scipy soundfile tqdm opencv-python-headless
# !apt-get install -q ffmpeg

# ══════════════════════════════════════════════════
# CELL 2: Clone repo
# ══════════════════════════════════════════════════

# Replace with your actual repo URL
REPO_URL = "https://github.com/YOUR_USERNAME/loopcanvas.git"
SERVER_URL = "https://your-server-url.com"  # Your Vercel/Oracle server

# import subprocess
# subprocess.run(["git", "clone", REPO_URL, "/content/loopcanvas"], check=True)

# ══════════════════════════════════════════════════
# CELL 3: Verify GPU
# ══════════════════════════════════════════════════

import torch
print(f"PyTorch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f}GB")
else:
    print("WARNING: No GPU detected. Switch runtime to GPU.")
    print("Runtime → Change runtime type → Hardware accelerator → GPU")

# ══════════════════════════════════════════════════
# CELL 4: Start worker
# ══════════════════════════════════════════════════

import sys
sys.path.insert(0, "/content/loopcanvas/loopcanvas_app/canvas-engine")

# For local testing without a server, use file queue:
# from queue.gpu_worker import GPUWorker
# worker = GPUWorker(local=True, worker_id="colab-free-t4", worker_type="colab")

# For connected mode with your server:
# from queue.gpu_worker import GPUWorker
# worker = GPUWorker(
#     server_url=SERVER_URL,
#     worker_id="colab-free-t4",
#     worker_type="colab"
# )

# Run continuously until Colab session ends
# worker.run_continuous(poll_interval=15, max_idle_minutes=60)

print("""
╔══════════════════════════════════════════════════════════════╗
║                 LoopCanvas Colab GPU Worker                   ║
╠══════════════════════════════════════════════════════════════╣
║                                                               ║
║  To activate:                                                 ║
║  1. Update REPO_URL and SERVER_URL above                      ║
║  2. Uncomment the install commands in Cell 1                  ║
║  3. Uncomment the git clone in Cell 2                         ║
║  4. Uncomment the worker start in Cell 4                      ║
║  5. Run all cells                                             ║
║                                                               ║
║  The worker will generate at FULL SDXL + SVD quality          ║
║  on the free T4 GPU and upload results to your server.        ║
║                                                               ║
║  Free Colab gives you ~4-12 hours of GPU per session.         ║
║  Each canvas takes ~30-90 seconds on T4.                      ║
║  That's ~200-1400 canvases per session. For free.             ║
╚══════════════════════════════════════════════════════════════╝
""")
