FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1 \
	PDM_CHECK_UPDATE=false \
	PDM_IGNORE_SAVED_PYTHON=1

WORKDIR /app

RUN apt-get update \
	&& apt-get install -y --no-install-recommends tini \
	&& rm -rf /var/lib/apt/lists/* \
	&& pip install --no-cache-dir "pdm>=2.22.0,<3"

COPY pyproject.toml /app/
RUN pdm config python.use_venv false \
	&& pdm install --prod --no-editable --no-lock

COPY . /app

RUN groupadd --system --gid 10001 appuser \
	&& useradd --system --uid 10001 --gid 10001 --create-home --home-dir /home/appuser --shell /usr/sbin/nologin appuser \
	&& mkdir -p /app/data/keyboxes /app/data/session /app/logs \
	&& chown -R appuser:appuser /app \
	&& chmod 750 /app/data /app/data/keyboxes /app/data/session /app/logs

ENV PYTHONPATH="/app/__pypackages__/3.14/lib"

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
	CMD python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('/app/data/keyboxes').exists() else 1)"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "scavenger_main.py"]
