# Webhooks

Webhooks notify your integration about asynchronous events such as analysis completion, render completion, and failures.

## Why webhooks

- Rendering is asynchronous and can take minutes
- Webhooks are the most reliable way to react to completion
- They reduce polling and prevent unnecessary retries
- You get notified the moment something happens

## Setting up webhooks

### 1. Create an endpoint

Create an HTTPS endpoint on your server that accepts POST requests:

```python
from flask import Flask, request

app = Flask(__name__)

@app.route("/webhooks/loopcanvas", methods=["POST"])
def handle_webhook():
    event = request.json

    if event["type"] == "canvas.completed":
        canvas = event["data"]
        download_url = canvas["exports"]["mp4_720x1280"]
        # Process the completed canvas

    return "", 200
```

### 2. Register in dashboard

Add your endpoint URL in the [Dashboard](https://dashboard.loopcanvas.com/webhooks).

### 3. Verify signatures

Webhook requests include a signature header for verification:

```python
import hmac
import hashlib

def verify_signature(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

@app.route("/webhooks/loopcanvas", methods=["POST"])
def handle_webhook():
    signature = request.headers.get("X-Signature")
    if not verify_signature(request.data.decode(), signature, WEBHOOK_SECRET):
        return "Invalid signature", 401

    # Process event...
```

## Event types

### Track events

| Event | Description |
|-------|-------------|
| `track.analyzed` | Analysis complete, ready for generation |
| `track.analysis_failed` | Analysis failed |

### Canvas events

| Event | Description |
|-------|-------------|
| `canvas.completed` | Canvas render complete |
| `canvas.failed` | Canvas render failed |

### Video events

| Event | Description |
|-------|-------------|
| `video.completed` | Video render complete |
| `video.failed` | Video render failed |

### Render events

| Event | Description |
|-------|-------------|
| `render.started` | Render job started |
| `render.progress` | Progress update (optional) |
| `render.completed` | Render finished successfully |
| `render.failed` | Render failed |

## Event structure

```json
{
  "id": "evt_abc123",
  "type": "canvas.completed",
  "created": 1707148800,
  "data": {
    "id": "canvas_xyz789",
    "track_id": "track_abc123",
    "status": "completed",
    "exports": {
      "mp4_720x1280": "https://cdn.loopcanvas.com/exports/canvas_xyz789.mp4"
    }
  }
}
```

## Delivery

### Retries

Failed deliveries are retried with exponential backoff:

| Attempt | Delay |
|---------|-------|
| 1 | Immediate |
| 2 | 1 minute |
| 3 | 5 minutes |
| 4 | 30 minutes |
| 5 | 2 hours |

After 5 failed attempts, the event is marked as failed.

### Timeouts

Respond within **30 seconds** or the request will timeout and be retried.

### Ordering

Events may arrive out of order. Use the `created` timestamp to determine sequence.

## Best practices

### Acknowledge quickly

Return `2xx` immediately, then process asynchronously:

```python
import threading

@app.route("/webhooks/loopcanvas", methods=["POST"])
def handle_webhook():
    event = request.json

    # Process async
    thread = threading.Thread(target=process_event, args=(event,))
    thread.start()

    # Return immediately
    return "", 200
```

### Be idempotent

Events may be delivered more than once. Use `event.id` to deduplicate:

```python
def process_event(event):
    if is_already_processed(event["id"]):
        return

    # Process...

    mark_as_processed(event["id"])
```

### Handle failures gracefully

Log failures and set up alerts for repeated webhook failures.

## Testing webhooks

### Use test mode

Test webhooks are sent for events in test mode, allowing you to validate your integration without charges.

### Local development

Use a tunnel service like ngrok to receive webhooks locally:

```bash
ngrok http 5000
# Use the https URL in your webhook settings
```

### Replay events

Replay failed events from the Dashboard for debugging.

## Next steps

- [Idempotency](./idempotency.md) — Ensure safe retries
- [Errors](./errors.md) — Handle error responses
