ARG WORKDIR="/szurubooru-toolkit"

FROM python:3.11-slim

ARG WORKDIR
# Optional dependency extras to install, passed straight to `uv sync`.
# Note: wd-tagger and wd-tagger-cuda conflict, so `--all-extras` doesn't work;
# list extras explicitly.
# Examples:
#   EXTRAS=""                              -> slim, no extras (default)
#   EXTRAS="--extra wd-tagger"             -> local WD tagger (ONNX Runtime + ffmpeg)
#   EXTRAS="--extra wd-tagger-cuda"        -> WD tagger with CUDA acceleration
#   EXTRAS="--extra pixiv"                 -> Pixiv metadata support
#   EXTRAS="--extra wd-tagger --extra pixiv" -> everything (CPU tagger)
ARG EXTRAS=""

# Don't buffer `stdout`:
ENV PYTHONUNBUFFERED=1
# Don't create `.pyc` files:
ENV PYTHONDONTWRITEBYTECODE=1

# ffmpeg is only needed for WD tagger video frame sampling, so install it only
# when the wd-tagger extra is being built.
RUN apt-get update && apt-get install -y \
  libssl-dev \
  libffi-dev \
  python3-dev \
  cron \
  && case " $EXTRAS " in *"wd-tagger"*) apt-get install -y ffmpeg ;; esac \
  && rm -rf /var/lib/apt/lists/*
RUN pip3 install --upgrade pip && \
  pip3 install "uv>=0.11.6"

WORKDIR ${WORKDIR}
COPY . .

COPY uv.lock pyproject.toml README.md ./
RUN uv sync --frozen --no-dev $EXTRAS

# The environment is fully baked above; without this, every `uv run` re-syncs
# against the lockfile and uninstalls the extras. Cron jobs don't inherit ENV,
# so entrypoint.sh sets it in the installed crontab as well.
ENV UV_NO_SYNC=1

RUN chmod +x /szurubooru-toolkit/entrypoint.sh
CMD ["/szurubooru-toolkit/entrypoint.sh"]
