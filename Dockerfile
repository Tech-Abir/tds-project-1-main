# Use official Python
FROM python:3.11

# Create user required by Hugging Face Spaces
RUN useradd -m -u 1000 user

# Set working directory
WORKDIR /app

# Copy requirements to container
COPY --chown=user requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Copy everything (including root and app subfolder)
COPY --chown=user . /app

# Switch to non-root user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Command to run FastAPI app (entrypoint: app.main:app)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
