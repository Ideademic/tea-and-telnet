# Tea & Telnet — pure-stdlib Python, so the image is tiny and has no deps.
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Tea & Telnet" \
      org.opencontainers.image.description="A cozy mini BBS served over telnet" \
      org.opencontainers.image.source="https://github.com/Ideademic/tea-and-telnet"

# Don't run as root.
RUN useradd --create-home --uid 10001 bbs

WORKDIR /app
COPY teaandtelnet ./teaandtelnet

ENV TT_HOST=0.0.0.0 \
    TT_PORT=2323 \
    TT_DB=/data/teaandtelnet.db \
    PYTHONUNBUFFERED=1

# Persist users, posts and chat history here.
RUN mkdir -p /data && chown bbs:bbs /data
VOLUME ["/data"]
USER bbs

EXPOSE 2323
CMD ["python", "-m", "teaandtelnet"]
