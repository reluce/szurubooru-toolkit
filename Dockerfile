ARG WORKDIR="/szurubooru-toolkit"

FROM python:3.10

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
  pip3 install poetry

WORKDIR ${WORKDIR}
COPY . .

COPY poetry.lock pyproject.toml README.md ./
RUN poetry config virtualenvs.create false && \
  poetry install --only main --ansi --no-interaction

VOLUME /etc/cron.d/crontab
VOLUME /szurubooru-toolkit/config.toml
VOLUME /szurubooru-toolkit/temp
VOLUME /szurubooru-toolkit/misc
VOLUME /szurubooru-toolkit/szurubooru_toolkit.log

RUN chmod +x /szurubooru-toolkit/entrypoint.sh
CMD ["/szurubooru-toolkit/entrypoint.sh"]
