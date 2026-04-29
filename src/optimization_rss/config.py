import os
from pathlib import Path

ARXIV_CATEGORIES = ["math.OC", "cs.MS", "cs.LG"]

OPTIMIZATION_KEYWORDS = [
    "convex optimization",
    "linear programming",
    "integer programming",
    "mixed integer",
    "stochastic optimization",
    "nonlinear programming",
    "robust optimization",
    "combinatorial optimization",
    "semidefinite programming",
    "quadratic programming",
    "gradient descent",
    "dual decomposition",
    "lagrangian relaxation",
    "branch and bound",
    "simplex method",
    "interior point",
]

SEMANTIC_SCHOLAR_QUERIES = [
    "mathematical optimization",
    "convex optimization",
    "linear programming",
    "integer programming",
    "stochastic optimization",
]

LOOKBACK_DAYS = 7
MAX_PAPERS_PER_SOURCE = 100

FEED_TITLE = "Mathematical Optimization Papers"
FEED_DESCRIPTION = "Latest papers on mathematical optimization from arXiv and Semantic Scholar"
FEED_LINK = "https://koki-kazaore.github.io/mathematical-optimization-papers-rss/feed.xml"

STATE_FILE = Path("data/state.json")
FEED_FILE = Path("docs/feed.xml")

SEMANTIC_SCHOLAR_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
