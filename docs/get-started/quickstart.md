# Quickstart

This guide walks you through a complete flow:

1. Create a Track
2. Generate a Canvas
3. Expand into a full-length Video
4. Receive a webhook when the render is ready

## What you'll need

- An API key (test mode is free)
- An audio file (or audio URL)
- A webhook endpoint (recommended)

## How the API behaves

- Most creates return immediately and start async work
- You'll receive completion events via webhook (or you can poll)
- You're billed only when a job completes successfully

---

## Step 1: Create a Track

Upload your audio file to create a Track.

```bash
curl https://api.loopcanvas.com/v1/tracks \
  -H "Authorization: Bearer sk_test_..." \
  -F "file=@track.mp3" \
  -F "title=My Song" \
  -F "artist=Artist Name"
```

Response:

```json
{
  "id": "track_abc123",
  "status": "analyzing",
  "title": "My Song",
  "artist": "Artist Name",
  "duration": null,
  "analysis": null
}
```

The Track is now being analyzed. Wait for the `track.analyzed` webhook or poll the Track endpoint.

---

## Step 2: Generate a Canvas

Once analysis is complete, create a Canvas:

```bash
curl https://api.loopcanvas.com/v1/canvases \
  -H "Authorization: Bearer sk_test_..." \
  -H "Content-Type: application/json" \
  -d '{
    "track_id": "track_abc123",
    "template_id": "memory_in_motion"
  }'
```

Response:

```json
{
  "id": "canvas_xyz789",
  "track_id": "track_abc123",
  "template_id": "memory_in_motion",
  "status": "rendering",
  "render_id": "render_def456"
}
```

---

## Step 3: Wait for completion

### Option A: Webhook (recommended)

Configure a webhook endpoint in your dashboard. You'll receive:

```json
{
  "type": "canvas.completed",
  "data": {
    "id": "canvas_xyz789",
    "status": "completed",
    "exports": {
      "mp4_720x1280": "https://cdn.loopcanvas.com/exports/canvas_xyz789.mp4"
    }
  }
}
```

### Option B: Polling

```bash
curl https://api.loopcanvas.com/v1/canvases/canvas_xyz789 \
  -H "Authorization: Bearer sk_test_..."
```

---

## Step 4: Download your Canvas

Once completed, download the export:

```bash
curl -o canvas.mp4 "https://cdn.loopcanvas.com/exports/canvas_xyz789.mp4"
```

---

## Step 5: Expand to full video (optional)

Create a full-length Video from the same visual world:

```bash
curl https://api.loopcanvas.com/v1/videos \
  -H "Authorization: Bearer sk_test_..." \
  -H "Content-Type: application/json" \
  -d '{
    "track_id": "track_abc123",
    "canvas_id": "canvas_xyz789",
    "aspect_ratio": "9:16"
  }'
```

---

## Complete example

```python
import requests

API_KEY = "sk_test_..."
BASE_URL = "https://api.loopcanvas.com/v1"

headers = {"Authorization": f"Bearer {API_KEY}"}

# 1. Upload track
with open("track.mp3", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/tracks",
        headers=headers,
        files={"file": f},
        data={"title": "My Song", "artist": "Artist"}
    )
track = response.json()

# 2. Wait for analysis (simplified - use webhooks in production)
import time
while track["status"] == "analyzing":
    time.sleep(5)
    track = requests.get(f"{BASE_URL}/tracks/{track['id']}", headers=headers).json()

# 3. Generate canvas
response = requests.post(
    f"{BASE_URL}/canvases",
    headers=headers,
    json={"track_id": track["id"], "template_id": "memory_in_motion"}
)
canvas = response.json()

# 4. Wait for render
while canvas["status"] == "rendering":
    time.sleep(10)
    canvas = requests.get(f"{BASE_URL}/canvases/{canvas['id']}", headers=headers).json()

# 5. Download
print(f"Canvas ready: {canvas['exports']['mp4_720x1280']}")
```

---

## Next steps

- [Authentication](./authentication.md) — Understand API keys and environments
- [Webhooks](./webhooks.md) — Set up reliable event delivery
- [Templates](../concepts/templates.md) — Control your visual style
