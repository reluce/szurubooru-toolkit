ARG WORKDIR="/szurubooru-toolkit"

FROM python:3.11

ARG WORKDIR

# Don't buffer `stdout`:
ENV PYTHONUNBUFFERED=1
# Don't create `.pyc` files:
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y \
  build-essential \
  libssl-dev \
  libffi-dev \
  python3-dev \
  cargo \
  cron
RUN pip3 install --upgrade pip && \
  pip3 install uv

WORKDIR ${WORKDIR}
COPY . .

COPY uv.lock pyproject.toml README.md ./
RUN uv sync --frozen --no-dev

RUN chmod +x /szurubooru-toolkit/entrypoint.sh
CMD ["/szurubooru-toolkit/entrypoint.sh"]
