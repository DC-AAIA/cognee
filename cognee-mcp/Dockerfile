# Build the MCP App workspace bundle (React/Vite, served inline by the MCP
# server). Vite writes to ../src/app_bundles/ relative to apps-src, so we
# mirror the repo layout: /build/cognee-mcp/{apps-src,src}.
# DC immutable build: base image pinned by exact registry digest.
FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS app-bundle
WORKDIR /build/cognee-mcp/apps-src
COPY ./cognee-mcp/apps-src/package.json ./cognee-mcp/apps-src/package-lock.json ./
RUN npm ci
COPY ./cognee-mcp/apps-src ./
RUN npm run build
# Output lands at /build/cognee-mcp/src/app_bundles/visualize-graph.html

# Use a Python image with uv pre-installed.
# DC immutable build: base image pinned by exact registry digest for reproducibility.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS uv

# Install the project preserving the repo layout so that the
# [tool.uv.sources] cognee = { path = "..", package = true } override in
# cognee-mcp/pyproject.toml resolves the cognee engine from the same source
# tree at version 1.4.0, not from PyPI.
WORKDIR /app/cognee-mcp

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Set build arguments
ARG DEBUG
ARG GIT_COMMIT=unknown

# Set environment variable based on the build argument
ENV DEBUG=${DEBUG}

# Needed when psycopg2 is built from source via cognee[postgres] in linux images.
# libpq-dev provides pg_config; build-essential provides libc headers and toolchain.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the root repo files (pyproject.toml, README.md, uv.lock) and the engine
# packages (cognee, cognee_db_workers, distributed, kuzu) to /app/ so that the
# [tool.uv.sources] path = ".." override resolves to the local source tree at
# version 1.4.0. This ensures the engine and MCP are built from the same tree.
COPY pyproject.toml README.md uv.lock /app/
COPY cognee /app/cognee
COPY cognee_db_workers /app/cognee_db_workers
COPY distributed /app/distributed
COPY kuzu /app/kuzu

# Copy cognee-mcp pyproject.toml and lockfile first for better caching
COPY ./cognee-mcp/pyproject.toml ./cognee-mcp/uv.lock ./cognee-mcp/entrypoint.sh ./

# Install the project's dependencies using the lockfile and settings.
# --no-install-project skips installing cognee-mcp itself but installs its
# dependencies, including cognee 1.4.0 from the local path override.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --no-editable

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows layer caching
COPY ./cognee-mcp ./
# Drop in the workspace bundle built by the node stage. Order matters: the
# COPY above brings in `cognee-mcp/src/app_bundles/` (empty in CI/clean clones
# because the bundle is gitignored, or stale on a developer's machine), and
# this COPY then *shadows* it with the freshly-built bundle. uv sync below
# packages this into the wheel installed into the venv; visualize_graph_ui
# reads the bundle from its own neighbor directory inside site-packages.
COPY --from=app-bundle /build/cognee-mcp/src/app_bundles /app/cognee-mcp/src/app_bundles
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Build-time version assertions: verify the engine and MCP are built from the
# exact same source tree at the expected versions. Fails the build if either
# version does not match. Uses the venv Python (not system Python) so that
# importlib.metadata finds the installed packages.
ENV PATH="/app/cognee-mcp/.venv/bin:$PATH"
RUN python -c "import importlib.metadata; v=importlib.metadata.version('cognee'); assert v=='1.4.0', f'cognee version mismatch: got {v}, expected 1.4.0'" \
    && python -c "import importlib.metadata; v=importlib.metadata.version('cognee-mcp'); assert v=='0.5.4', f'cognee-mcp version mismatch: got {v}, expected 0.5.4'"

# Runtime stage: base image pinned by exact registry digest for reproducibility.
FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b

ARG GIT_COMMIT=unknown

# Install security updates for OS packages, then install runtime deps.
# apt-get upgrade addresses CVEs in the base image's OS packages (zlib,
# sqlite, ncurses, perl, etc.) that are flagged by Trivy.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
       libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtual environment and project from the uv stage.
# The repo layout is preserved: /app/cognee-mcp/ has the venv and entrypoint,
# /app/ has the engine packages (cognee, cognee_db_workers, distributed, kuzu).
COPY --from=uv /usr/local /usr/local
COPY --from=uv /app /app

# Strip Windows carriage returns (fixes "no such file" on Windows Docker)
RUN sed -i 's/\r$//' /app/cognee-mcp/entrypoint.sh && chmod +x /app/cognee-mcp/entrypoint.sh

# Run as a non-root user. Create the user before copying ownership so the
# /app tree (which already exists from the COPY above) is readable.
RUN groupadd --system --gid 1000 cognee \
    && useradd --system --uid 1000 --gid cognee --no-create-home --shell /usr/sbin/nologin cognee \
    && chown -R cognee:cognee /app

# Place executables in the environment at the front of the path
ENV PATH="/app/cognee-mcp/.venv/bin:$PATH"

# Set environment variables for MCP server
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/cognee-mcp
# Give the non-root user a stable, writable HOME so Kuzu/Ladybug caches its
# downloaded extensions in a consistent location across build and runtime.
ENV HOME=/app

# OCI provenance labels (immutable build metadata)
LABEL org.opencontainers.image.title="cognee-mcp"
LABEL org.opencontainers.image.description="Cognee MCP Server - DC immutable build from v1.4.0 source tree"
LABEL org.opencontainers.image.version="1.4.0-dc.1"
LABEL org.opencontainers.image.source="https://github.com/DC-AAIA/cognee"
LABEL org.opencontainers.image.revision="${GIT_COMMIT}"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.base.name="python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b"
LABEL io.dc.build.source-commit="${GIT_COMMIT}"
LABEL io.dc.build.engine-version="1.4.0"
LABEL io.dc.build.mcp-version="0.5.4"
LABEL io.dc.build.base-image-digest="sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b"

USER cognee

# Pre-install Kuzu/Ladybug's JSON extension at build time (network is available
# here) so it is baked into the image. Runs the same install path the app uses,
# as the same user with the same HOME, so the cached extension lands exactly
# where the running server looks for it — avoiding the "Extension: json ... has
# not been installed" Binder error when recall runs in a network-restricted
# container. Best-effort: a failed download must not break the image build.
RUN python -c "from cognee_db_workers._kuzu_helpers import install_json_extension_local; install_json_extension_local(buffer_pool_size=268435456)" \
    || echo "WARNING: JSON extension pre-install skipped (no network at build time); it will be installed on first run if the container has network access."

# Use the application name from pyproject.toml for normal operation
# For testing, we'll override this with a direct command
ENTRYPOINT ["/app/cognee-mcp/entrypoint.sh"]
