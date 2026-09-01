"""FastAPI app: serves the page, the sample, and POST /check."""

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from vouch.check import check
from vouch.config import build_prose_checker

STATIC = Path(__file__).parent / "static"
# The sample lives at the repo root because the spec names that path. It is only there when
# running from a checkout, which is the only way this app is meant to run.
SAMPLES = Path(__file__).resolve().parents[2] / "samples"

app = FastAPI(title="Vouch", docs_url=None, redoc_url=None)


class CheckRequest(BaseModel):
    draft: str
    facts: str


@app.get("/")
def page() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/sample")
def sample() -> dict:
    return {
        "draft": (SAMPLES / "draft.txt").read_text(encoding="utf-8"),
        "facts": (SAMPLES / "facts.txt").read_text(encoding="utf-8"),
    }


@app.post("/check")
def run_check(req: CheckRequest) -> dict:
    return check(req.draft, req.facts, build_prose_checker()).to_dict()


def main() -> None:
    uvicorn.run("vouch.app:app", host="127.0.0.1", port=8000)
