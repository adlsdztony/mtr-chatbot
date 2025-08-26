## Run with Docker (Development Mode)

### Prerequisites
These prerequisites are already installed if you are using innowing's computer.
- Docker and Docker Compose installed
- **NVIDIA GPU Support Required (if you use cpu only, ignore this)**:
  - NVIDIA GPU with CUDA support
  - NVIDIA Container Toolkit installed
  - Docker configured for GPU access

### Build and Run
#### Run with gpu
```bash
# Run in detached mode
docker compose up -d --build

# Pull necessary Ollama models (example)
docker exec -it mtr-ollama ollama pull deepseek-r1:8b
```
Verify GPU Usage in Ollama:
```bash
# Check if Ollama is using nvidia GPU
docker exec mtr-ollama nvidia-smi
```
#### Or run with cpu only
```bash
# Run in detached mode
docker compose up -f docker-compose.cpu.yml -d --build

# Pull necessary Ollama models (example)
docker exec -it mtr-ollama ollama pull deepseek-r1:8b
```
Now you can access the application at http://localhost:8501

### Run embedding
No need if the processed data `database\storage\<id>` already exists
```bash
# need to use qwen2.5vl:72b which is too large for laptop
uv run tests\run_embedding.py
```

### View the logs
```bash
# view the logs
docker compose logs -f
# view the chatbot logs only
docker compose logs -f chatbot
```

### Access the Application
- Chatbot: http://localhost:8501
- Ollama API: http://localhost:11434

### Change Models
You can change the models used by modifying the `docker-compose.yml` file. For example, to change the model for Ollama, update the `OLLAMA_CHAT_MODEL` environment variable in the `mtr-ollama` service section.

After making changes to the `docker-compose.yml` file, restart the services:
```bash
docker compose restart mtr-ollama mtr-chatbot
```

After restarting the services, pull required models:
```bash
docker exec mtr-ollama ollama pull deepseek-r1:8b
docker exec mtr-ollama ollama pull qwen2.5vl:72b
docker exec mtr-ollama ollama pull bge-m3:latest
# or any other model you need
```

