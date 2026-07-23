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
# The rest are system libraries required by kaleido (headless Chromium,
# used to render Plotly charts into the PDF report) and by common ML wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git git-lfs \
    wget ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libgbm1 \
    libasound2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libxkbcommon0 libpango-1.0-0 libpangocairo-1.0-0 fonts-liberation \
    libx11-xcb1 libxext6 libxi6 libxtst6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /repo

# Install Python deps first so this layer is cached across code-only changes.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    -r backend/requirements.txt

# kaleido >=1.0 no longer bundles a Chromium binary (unlike the 0.2.x series
# the apt packages above were originally chosen for) — it launches a
# separately-downloaded Chrome instead. On a dev machine that already has
# Chrome/Edge installed, kaleido finds it automatically; a fresh container
# has neither, so this step is required or PDF report generation fails.
RUN plotly_get_chrome -y

# Only what the backend actually reads at runtime.
COPY backend/ backend/
COPY modules/ modules/
COPY assets/ assets/

WORKDIR /repo/backend

# Hugging Face Spaces (Docker SDK) expects the app on port 7860 by default.
ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
