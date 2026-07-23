# Backend image for Hugging Face Spaces (Docker SDK).
# Builds the FastAPI app in backend/, which also needs modules/ (ML models:
# K-Means clustering, PPO agents) and assets/ (email logo) from the repo
# root — see ROOT-relative path logic in backend/app/db.py, clustering.py,
# and email_service.py.

FROM python:3.13-slim

# git + git-lfs: Hugging Face Spaces' build platform runs git commands
# inside the image early in the build (to resolve LFS-tracked files such as
# the PPO model weights and PNGs) — without these, the build fails before
# it even reaches our own steps below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git git-lfs \
    wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /repo

# Install Python deps first so this layer is cached across code-only changes.
# PDF report charts are rendered with matplotlib, not plotly+kaleido — a
# headless-Chromium subprocess crashed this Space when run alongside the
# already-loaded PyTorch/FinBERT models (tried kaleido>=1.0's downloaded
# Chrome, then reverted to 0.2.1's bundled one; both crashed it). matplotlib
# needs no browser/subprocess and has a much smaller memory footprint.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    -r backend/requirements.txt

# Only what the backend actually reads at runtime.
COPY backend/ backend/
COPY modules/ modules/
COPY assets/ assets/

WORKDIR /repo/backend

# Hugging Face Spaces (Docker SDK) expects the app on port 7860 by default.
ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
