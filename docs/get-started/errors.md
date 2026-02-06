# Errors

We use conventional HTTP response codes and return a structured error object.

## HTTP status codes

| Code | Meaning |
|------|---------|
| `200–299` | Success |
| `400` | Invalid request (missing/invalid params) |
| `401` | Authentication error |
| `403` | Permission error |
| `404` | Resource not found |
| `409` | Conflict (idempotency or state conflict) |
| `422` | Unprocessable (validation failed) |
| `429` | Rate limit exceeded |
| `5xx` | Server errors |

## Error structure

All errors return a consistent structure:

```json
{
  "error": {
    "type": "invalid_request_error",
    "message": "The track_id parameter is required",
    "param": "track_id",
    "request_id": "req_abc123"
  }
}
```

### Fields

| Field | Description |
|-------|-------------|
| `type` | Stable error type for programmatic handling |
| `message` | Human-readable explanation |
| `param` | Which parameter caused the error (if applicable) |
| `request_id` | Unique ID for support requests |

## Error types

| Type | Meaning |
|------|---------|
| `authentication_error` | Invalid or missing API key |
| `permission_error` | Key lacks required permissions |
| `invalid_request_error` | Request has invalid parameters |
| `not_found_error` | Resource doesn't exist |
| `conflict_error` | State or idempotency conflict |
| `rate_limit_error` | Too many requests |
| `api_error` | Server-side problem |

## Handling errors

### Client errors (4xx)

Don't retry these automatically—fix the request first.

```python
response = requests.post(url, json=data)
if response.status_code == 400:
    error = response.json()["error"]
    print(f"Invalid request: {error['message']}")
    if error.get("param"):
        print(f"Check parameter: {error['param']}")
```

### Rate limits (429)

Retry with exponential backoff:

```python
import time

def make_request_with_retry(url, data, max_retries=3):
    for attempt in range(max_retries):
        response = requests.post(url, json=data)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            time.sleep(retry_after)
            continue
        return response
    raise Exception("Max retries exceeded")
```

### Server errors (5xx)

Retry with exponential backoff:

```python
def make_request_with_retry(url, data, max_retries=3):
    for attempt in range(max_retries):
        response = requests.post(url, json=data)
        if response.status_code >= 500:
            time.sleep(2 ** attempt)  # 1, 2, 4 seconds
            continue
        return response
    raise Exception("Max retries exceeded")
```

### Conflict errors (409)

Usually indicates:
- Duplicate idempotency key with different parameters
- Resource in invalid state for operation

Check the original request and current state before retrying.

## Debugging

### Use request_id

Include the `request_id` when contacting support:

```
"I received an error with request_id: req_abc123"
```

### Check the dashboard

View request logs in your [Dashboard](https://dashboard.loopcanvas.com/logs) for detailed debugging.

## Next steps

- [Rate limits](./rate-limits.md) — Understand throughput limits
- [Idempotency](./idempotency.md) — Safe retry patterns
