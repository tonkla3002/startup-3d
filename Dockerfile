FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/srv/.venv \
    PATH="/srv/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /srv

# ติดตั้ง dependency ก่อน copy โค้ด เพื่อให้ layer นี้ cache ได้เวลาโค้ดเปลี่ยน
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ต้องมี alembic/ กับ alembic.ini ด้วย ไม่งั้น migrate ใน container ไม่ได้
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY deploy/entrypoint.sh ./deploy/entrypoint.sh
RUN chmod +x ./deploy/entrypoint.sh && uv sync --frozen --no-dev

# รันด้วย user ที่ไม่ใช่ root
# runtime เรียก binary ใน /srv/.venv ตรง ๆ ไม่ผ่าน `uv run`
# เพราะ uv ต้องเขียน cache ที่ $HOME ซึ่ง non-root user เขียนไม่ได้
RUN useradd -r -u 10001 -m -d /home/streamora streamora \
    && chown -R streamora:streamora /srv /home/streamora
USER streamora

EXPOSE 8000
ENTRYPOINT ["./deploy/entrypoint.sh"]
CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
