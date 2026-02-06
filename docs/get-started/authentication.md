# Authentication

Authenticate using your API key. Your key determines whether requests run in **test** or **live** mode.

## API keys

| Key prefix | Mode | Purpose |
|------------|------|---------|
| `sk_test_` | Test | Development and validation |
| `sk_live_` | Live | Production traffic |

### Test mode
- Free to use while building
- Outputs are watermarked
- No billing charges
- Data doesn't appear in live mode

### Live mode
- Production-quality outputs
- No watermarks
- Usage is billed
- Full analytics and reporting

## Using your API key

Include your key in the `Authorization` header:

```bash
curl https://api.loopcanvas.com/v1/tracks \
  -H "Authorization: Bearer sk_test_your_key_here"
```

## Best practices

### Keep keys secret
- Never commit keys to version control
- Use environment variables
- Rotate keys if exposed

### Don't embed in client-side apps
- API keys should only be used server-side
- For client apps, create a backend proxy

### Use separate keys per environment
- Development, staging, production
- For multi-tenant products, consider separate projects

## Key management

### Get your keys
Keys are available in your [Dashboard](https://dashboard.loopcanvas.com/api-keys).

### Rotate keys
1. Generate a new key in the dashboard
2. Update your applications
3. Delete the old key

### Restrict key permissions
Enterprise plans support scoped keys with limited permissions.

## Error responses

| Code | Meaning |
|------|---------|
| `401` | Invalid API key |
| `401` | Missing API key |
| `403` | Key doesn't have required permissions |

```json
{
  "error": {
    "type": "authentication_error",
    "message": "Invalid API key provided",
    "request_id": "req_abc123"
  }
}
```

## Next steps

- [API versions](./api-versions.md) — Pin your API version
- [Errors](./errors.md) — Handle errors gracefully
