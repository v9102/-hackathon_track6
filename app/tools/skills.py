"""Canonical skill normalization and extraction.

Skills are compared using a controlled alias dictionary so that, e.g.,
``Node``/``Node.js``/``NodeJS`` are all normalized to ``Node.js`` while
technically different technologies stay distinct (``Git`` != ``GitHub``,
``SQL`` != ``PostgreSQL``).

The evaluator compares canonicalized skills rather than raw strings.
"""

from __future__ import annotations

import re

# canonical skill -> its recognized aliases (aliases are matched as whole tokens)
CANONICAL_ALIASES: dict[str, list[str]] = {
    "Python": ["python", "python3"],
    "Java": ["java"],
    "Go": ["golang", "go"],
    "Rust": ["rust"],
    "C++": ["c++"],
    "C#": ["c#", "csharp"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript", "ts"],
    "HTML/CSS": ["html", "css"],
    "React": ["react"],
    "React Native": ["react native", "react-native", "reactnative"],
    "Next.js": ["next.js", "nextjs"],
    "Angular": ["angular"],
    "Vue.js": ["vue", "vue.js", "vuejs"],
    "Redux": ["redux"],
    "Zustand": ["zustand"],
    "React Query": ["react query"],
    "Node.js": ["node", "node.js", "nodejs"],
    "Express.js": ["express", "express.js", "expressjs"],
    "REST API": ["rest api", "restful api", "rest"],
    "GraphQL": ["graphql"],
    "JWT": ["jwt"],
    "Auth": ["authentication", "auth"],
    "PostgreSQL": ["postgres", "postgresql"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Kafka": ["kafka"],
    "SQL": ["sql"],
    "SQLite": ["sqlite"],
    "Cosmos DB": ["cosmos db", "cosmosdb"],
    "Docker": ["docker", "dockerized"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud"],
    "Git": ["git"],
    "GitHub": ["github"],
    "GitHub Actions": ["github actions"],
    "GitLab": ["gitlab"],
    "Linux": ["linux"],
    "CI/CD": ["ci/cd", "ci-cd", "cicd"],
    "Jenkins": ["jenkins"],
    "Terraform": ["terraform"],
    "ArgoCD": ["argocd", "argo cd"],
    "Helm": ["helm"],
    "Prometheus": ["prometheus"],
    "Grafana": ["grafana"],
    "Spark": ["apache spark", "spark"],
    "TensorFlow": ["tensorflow", "tf"],
    "PyTorch": ["pytorch"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "OpenCV": ["opencv"],
    "Machine Learning": ["machine learning", "ml", "ai/ml"],
    "Deep Learning": ["deep learning"],
    "LLM": ["llm", "large language model"],
    "Azure OpenAI": ["azure openai"],
    "Firebase": ["firebase"],
    "Gradle": ["gradle"],
    "Razorpay": ["razorpay"],
    "FCM": ["fcm", "firebase cloud messaging"],
    "Expo": ["expo"],
    "sqlc": ["sqlc"],
    "Flask": ["flask"],
    "Django": ["django"],
    "FastAPI": ["fastapi"],
    "Gin": ["gin"],
    "Unit Testing": ["unit test", "unit testing", "pytest"],
    "Testing": ["testing"],
    "Agile": ["agile"],
    "Scrum": ["scrum"],
    "Data Structures": ["data structures", "dsa"],
    "Algorithms": ["algorithms"],
}

# prebuilt: canonical -> non-empty alias regexes (longest-first to be safe)
_ALIAS_RE: dict[str, list[re.Pattern[str]]] = {}

# inverted: every alias (lower, no spaces) maps to its canonical skill
_ALIAS_LOOKUP: dict[str, str] = {}

for _canonical, _aliases in CANONICAL_ALIASES.items():
    _ALIAS_RE[_canonical] = [
        re.compile(rf"(?<![A-Za-z0-9]){re.escape(a)}(?![A-Za-z0-9])", re.IGNORECASE)
        for a in sorted(_aliases, key=len, reverse=True)
    ]
    for _alias in _aliases:
        key = _alias.lower().replace(" ", "").replace("/", "").replace("-", "")
        if _alias is not None and _alias:
            _ALIAS_LOOKUP[key] = _canonical


def normalize_skill(raw: str) -> str:
    """Map a raw skill token to its canonical form (identity when unknown)."""
    key = raw.strip().lower().replace(" ", "").replace("/", "").replace("-", "")
    return _ALIAS_LOOKUP.get(key, raw.strip())


def extract_canonical_skills(text: str) -> set[str]:
    """Extract canonicalized skill names present in ``text``."""
    if not text:
        return set()
    found: set[str] = set()
    for canonical, patterns in _ALIAS_RE.items():
        for pat in patterns:
            if pat.search(text):
                found.add(canonical)
                break
    return found


def canonical_to_alias_forms(canonical: str) -> list[str]:
    """Return the aliases registered for a canonical skill."""
    return CANONICAL_ALIASES.get(canonical, [canonical])


def canonicalize_list(raw_skills: list[str] | set[str]) -> set[str]:
    """Canonicalize a raw skill list into its canonical set."""
    canonical: set[str] = set()
    for skill in raw_skills:
        canonical.add(normalize_skill(skill))
    return canonical