ARG WORKDIR="/szuru-toolkit"

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
VOLUME /szuru-toolkit/config.toml
VOLUME /szuru-toolkit/temp
VOLUME /szuru-toolkit/misc
VOLUME /szuru-toolkit/szurubooru_toolkit.log

RUN chmod +x /szuru-toolkit/entrypoint.sh
CMD ["/szuru-toolkit/entrypoint.sh"]
