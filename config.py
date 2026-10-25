# language: Python, file: config.py
# central config — edit key, model, chain here

NVIDIA_API_KEY = "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"
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"

# defaults — overridden by CLI flags
TARGET_CHAIN = "BTC"           # "BTC" or "ETH"
THREADS = 4
CANDIDATES_PER_BATCH = 50
CHECK_INTERVAL = 0.1           # seconds between blockchain API queries (rate limit)
LOG_FILE = "hits.log"

# LLM generation settings
LLM_TEMPERATURE = 0.9
LLM_TOP_P = 0.95
LLM_MAX_TOKENS = 2048
LLM_TIMEOUT = 30               # seconds

# worker settings
QUEUE_TIMEOUT = 5              # seconds to wait for queue item before worker exits
ROUND_DELAY = 2                # seconds between generation rounds