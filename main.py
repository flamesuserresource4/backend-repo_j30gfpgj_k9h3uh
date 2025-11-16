import os
import re
from datetime import datetime, timezone
from typing import List, Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field

from database import create_document, get_documents, db

app = FastAPI(title="Nikhil Lohia — Scriptwriter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Metric(BaseModel):
    views: Optional[int] = None
    avg_retention: Optional[float] = Field(default=None, description="Average retention percentage if provided manually")
    upload_date: Optional[str] = None
    last_updated: Optional[datetime] = None


class WorkItem(BaseModel):
    title: str
    channel: Optional[str] = None
    youtube_url: Optional[HttpUrl] = None
    thumbnail_url: Optional[HttpUrl] = None
    outcome: Optional[str] = None
    metrics: Metric = Field(default_factory=Metric)


class LogoItem(BaseModel):
    name: str
    image_url: HttpUrl
    link_url: Optional[HttpUrl] = None


YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
NOTION_PAGE_URL = os.getenv(
    "NOTION_PAGE_URL",
    "https://reinvented-salute-989.notion.site/Nikhil-Lohia-2aaf06f4560e8069ac8ff6149020cbe2",
)
DRIVE_FOLDER_ID = os.getenv(
    "GOOGLE_DRIVE_FOLDER_ID", "1AyDd3MiBoGe2zJdLaN2iRyGj8naJo4Np"
)


@app.get("/")
def read_root():
    return {"message": "Backend running", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


# -------- Utilities ---------

def extract_youtube_id(url: str) -> Optional[str]:
    try:
        # Handles youtu.be/ID, youtube.com/watch?v=ID, and with params
        short_match = re.search(r"youtu\.be/([\w-]{6,})", url)
        if short_match:
            return short_match.group(1)
        id_match = re.search(r"v=([\w-]{6,})", url)
        if id_match:
            return id_match.group(1)
        embed_match = re.search(r"/embed/([\w-]{6,})", url)
        if embed_match:
            return embed_match.group(1)
    except Exception:
        return None
    return None


def get_youtube_details(video_id: str):
    if not YOUTUBE_API_KEY:
        return None
    try:
        url = (
            "https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id="
            + video_id
            + "&key="
            + YOUTUBE_API_KEY
        )
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("items"):
            return None
        item = data["items"][0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        return {
            "title": snippet.get("title"),
            "channel": snippet.get("channelTitle"),
            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url"),
            "upload_date": snippet.get("publishedAt"),
            "views": int(stats.get("viewCount", 0)) if stats.get("viewCount") else None,
        }
    except Exception:
        return None


# -------- Data Endpoints ---------

@app.get("/api/notion/best-work", response_model=List[WorkItem])
def notion_best_work():
    """Attempt to read the public Notion page and extract YouTube links and titles.
    Fallback: return placeholders with the Notion link for manual update in the UI.
    """
    try:
        r = requests.get(NOTION_PAGE_URL, timeout=12)
        r.raise_for_status()
        html = r.text
        # Find candidate blocks of YouTube links
        links = re.findall(r'href="(https?:\\/\\/[^\"]+)"', html)
        yt_links = []
        for href in links:
            href = href.replace("\\/", "/")
            if "youtube.com/watch" in href or "youtu.be/" in href:
                yt_links.append(href)
        # De-duplicate preserving order
        seen = set()
        ordered = []
        for l in yt_links:
            if l not in seen:
                seen.add(l)
                ordered.append(l)
        ordered = ordered[:3]

        results: List[WorkItem] = []
        for l in ordered:
            vid = extract_youtube_id(l)
            details = get_youtube_details(vid) if vid else None
            item = WorkItem(
                title=details.get("title") if details else "YouTube Video",
                channel=details.get("channel") if details else None,
                youtube_url=l,
                thumbnail_url=details.get("thumbnail_url") if details else None,
                outcome=None,
                metrics=Metric(
                    views=details.get("views") if details else None,
                    avg_retention=None,
                    upload_date=details.get("upload_date") if details else None,
                    last_updated=datetime.now(timezone.utc),
                ),
            )
            results.append(item)
        if results:
            return results
    except Exception:
        pass

    # Fallback placeholders
    now = datetime.now(timezone.utc)
    return [
        WorkItem(
            title="Case Study Placeholder 1",
            channel="Channel Name",
            youtube_url=NOTION_PAGE_URL,
            thumbnail_url=None,
            outcome="N/A — add manually",
            metrics=Metric(views=None, avg_retention=None, upload_date=None, last_updated=now),
        ),
        WorkItem(
            title="Case Study Placeholder 2",
            channel="Channel Name",
            youtube_url=NOTION_PAGE_URL,
            thumbnail_url=None,
            outcome="N/A — add manually",
            metrics=Metric(views=None, avg_retention=None, upload_date=None, last_updated=now),
        ),
        WorkItem(
            title="Case Study Placeholder 3",
            channel="Channel Name",
            youtube_url=NOTION_PAGE_URL,
            thumbnail_url=None,
            outcome="N/A — add manually",
            metrics=Metric(views=None, avg_retention=None, upload_date=None, last_updated=now),
        ),
    ]


class MetricsRequest(BaseModel):
    url: HttpUrl
    manual_retention_pct: Optional[float] = None


@app.post("/api/youtube/metrics", response_model=WorkItem)
def refresh_metrics(req: MetricsRequest):
    vid = extract_youtube_id(str(req.url))
    if not vid:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    details = get_youtube_details(vid)
    now = datetime.now(timezone.utc)
    return WorkItem(
        title=details.get("title") if details else "YouTube Video",
        channel=details.get("channel") if details else None,
        youtube_url=str(req.url),
        thumbnail_url=details.get("thumbnail_url") if details else None,
        outcome=None,
        metrics=Metric(
            views=details.get("views") if details else None,
            avg_retention=req.manual_retention_pct,
            upload_date=details.get("upload_date") if details else None,
            last_updated=now,
        ),
    )


# Simple logo storage using DB
LOGO_COLLECTION = "logo"


@app.get("/api/logos")
def list_logos(limit: int = 50):
    try:
        docs = get_documents(LOGO_COLLECTION, {}, limit)
        # Convert ObjectId and datetime to strings
        out = []
        for d in docs:
            d["_id"] = str(d.get("_id"))
            for k, v in list(d.items()):
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
            out.append(d)
        return out
    except Exception as e:
        return []


@app.post("/api/logos")
def add_logo(item: LogoItem):
    try:
        _id = create_document(LOGO_COLLECTION, item)
        return {"inserted_id": _id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/drive/embed")
def drive_embed():
    # Provide a public embeddable URL for the folder grid view
    embed_url = f"https://drive.google.com/embeddedfolderview?id={DRIVE_FOLDER_ID}#grid"
    return {"embed_url": embed_url}
