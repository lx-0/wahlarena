FROM python:3.13-slim

# Install Node.js 24 (required for wahlomat_runner.js + Playwright)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (pinned)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node deps (pinned via package-lock.json)
COPY package.json package-lock.json ./
RUN npm ci

# Install Playwright browser (Chromium only)
RUN npx playwright install --with-deps chromium

# Copy project files
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY runs/ ./runs/

# Run tests by default; override CMD to reproduce results
CMD ["pytest", "tests/", "-v"]
