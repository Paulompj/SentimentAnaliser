"""
Configuracoes centralizadas do projeto.

Carrega variaveis de ambiente do arquivo .env e expoe as constantes
utilizadas pelos demais modulos.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega o .env que fica na raiz do projeto
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

# YouTube Data API
YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_API_BASE_URL: str = "https://www.googleapis.com/youtube/v3"

# Quantidade maxima de comentarios por pagina (max permitido pela API = 100)
COMMENTS_PER_PAGE: int = 100

# Ordenacao dos comentarios: "relevance" ou "time"
COMMENTS_ORDER: str = "relevance"
