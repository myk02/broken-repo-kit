# syntax=docker/dockerfile:1

# Pinned to a concrete Python 3.12 patch release. A digest is better still;
# record the digest here when the image is published to your registry.
FROM python:3.12.8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install the only third-party dependency first, so the layer is cached.
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

# The application is read-only for the unprivileged runtime user. Verification
# only ever writes to the system temp directory, so the repository can be
# mounted read-only.
RUN useradd --create-home --uid 10001 kit \
    && chown -R root:root /app \
    && chmod -R a+rX /app

USER kit

# Fail the build if the package metadata or the CLI is broken.
RUN python -m kit list > /dev/null

CMD ["python", "-m", "kit", "list"]
