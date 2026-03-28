FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy the project files
COPY . .

# Install dependencies using uv
RUN uv sync --frozen

# Expose the port (Render will override this, but good practice)
EXPOSE 8000

# Start the Uvicorn server
CMD ["uv", "run", "python", "server.py"]
