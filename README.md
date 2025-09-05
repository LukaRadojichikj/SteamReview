
# Steam Snapshots

CLI tool that fetches Steam reviews and summarizes them with Google Gemini.

## Features
- Fetches reviews from the **Steam API**
- Summarizes with **Gemini** (Google Generative AI)
- CLI built with **Typer + Rich** (pretty tables/JSON output)
- Fuzzy title matching, LLM caching, resilient HTTP retries
- Containerized with **Docker**
- Deployable as a **Kubernetes Job** with TTL cleanup

---

## Requirements
- **Python 3.11+**
- A Gemini API key in `.env`:
  ```env
  GEMINI_API_KEY=your_key_here
  ```
---

## Setup (local)

### Create venv

#### PowerShell (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

#### Bash (Linux/macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Usage (local)

Run the CLI by providing a game title:

#### PowerShell

```powershell
python main.py "<game title>" [OPTIONS]
```

#### Bash

```bash
python main.py "<game title>" [OPTIONS]
```

### Options

* `--count <N>` → number of reviews to fetch (default 3, max 20)
* `--format table|json` → output format (default: table)
* `--fuzzy` → enable fuzzy title matching (tolerates misspelling)
* `--out snapshots.json` → save output to a file
* `--no-cache` → disable LLM cache (always call Gemini)
* `--debug` → print raw reviews and Gemini responses

### Examples

#### PowerShell

```powershell
# 5 reviews in a table
python main.py "Celeste" --count 5 --format table

# Fuzzy matching for title
python main.py "Halflife" --fuzzy

# JSON output saved to a file
python main.py "Stardew Valley" --format json --out stardew.json
```

#### Bash

```bash
python main.py "Celeste" --count 5 --format table
python main.py "Halflife" --fuzzy
python main.py "Stardew Valley" --format json --out stardew.json
```

---

## Docker

#### PowerShell

```powershell
# Build the image
docker build -t steam-snapshots:latest .

# Run with .env and mount cache for LLM results
docker run --rm --env-file .env `
  -v "${PWD}\.cache:/app/.cache" `
  steam-snapshots:latest "<game title>" --count 3 --format table --fuzzy
```

#### Bash

```bash
docker build -t steam-snapshots:latest .

docker run --rm --env-file .env \
  -v "$(pwd)/.cache:/app/.cache" \
  steam-snapshots:latest "<game title>" --count 3 --format table --fuzzy
```

---

## Kubernetes (Docker Desktop, local image)

Create/update the Secret, apply the Job, then read logs.

#### PowerShell

```powershell
# Secret (do not commit your real key)
$Env:GEMINI_API_KEY="your_key_here"
kubectl create secret generic gemini-api `
  --from-literal=GEMINI_API_KEY="$Env:GEMINI_API_KEY" `
  --dry-run=client -o yaml | kubectl apply -f -

# Apply Job
kubectl apply -f k8s\job.yaml

# Read logs
kubectl logs job/steam-snapshots-job
```

#### Bash

```bash
GEMINI_API_KEY="your_key_here"
kubectl create secret generic gemini-api \
  --from-literal=GEMINI_API_KEY="$GEMINI_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f k8s/job.yaml
kubectl logs job/steam-snapshots-job
```

### Cleanup

#### PowerShell

```powershell
kubectl delete -f k8s\job.yaml
kubectl delete secret gemini-api
```

#### Bash

```bash
kubectl delete -f k8s/job.yaml
kubectl delete secret gemini-api
```

> The Job auto-deletes after the TTL configured in `k8s/job.yaml` (e.g., `ttlSecondsAfterFinished: 600`).

---

## Project structure

```
.
├─ main.py
├─ steam.py
├─ llm.py
├─ requirements.txt
├─ Dockerfile
├─ .dockerignore
├─ .gitignore
└─ k8s/
   └─ job.yaml
```

## Notes

* Do **not** commit your `.env`. Keep `./.env.example` with placeholders.
* If you change code, rebuild the image before re-running locally or in K8s:

  ```powershell
  docker build -t steam-snapshots:latest .
  ```