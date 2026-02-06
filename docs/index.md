# Music Visuals API Documentation

## Overview

The Music Visuals API generates **Spotify-style 7-second Canvases** and **full-length music videos** from audio.

The API is built for production workflows:

* Predictable, resource-oriented endpoints
* Async rendering with webhooks
* Idempotency for safe retries
* Usage-based billing and per-object cost attribution
* Licensing metadata on every output

### Use the API to:

* Generate visuals on-demand for creators
* Automate catalog-wide production for labels and distributors
* Enforce consistent style using templates

---

## What makes this different

This API is powered by a **proprietary, music-first video generation model** designed specifically for music visuals.

It's built to:

* Align edits to song structure (sections + energy)
* Tempo-lock motion and pacing to BPM
* Generate loop-native Canvases that loop cleanly
* Enforce style consistency via templates
* Support commercial workflows with rights-safe assets and provenance metadata

The goal is to behave like a **programmable music video editor**: fast, consistent, and controllable at scale.

---

## Documentation sections

### Get started
- [Overview](./get-started/overview.md)
- [Quickstart](./get-started/quickstart.md)
- [Authentication](./get-started/authentication.md)
- [API versions](./get-started/api-versions.md)
- [Idempotency](./get-started/idempotency.md)
- [Errors](./get-started/errors.md)
- [Rate limits](./get-started/rate-limits.md)
- [Pagination](./get-started/pagination.md)
- [Expanding responses](./get-started/expanding-responses.md)
- [Webhooks](./get-started/webhooks.md)

### Core concepts
- [Tracks](./concepts/tracks.md)
- [Analysis](./concepts/analysis.md)
- [Canvases](./concepts/canvases.md)
- [Videos](./concepts/videos.md)
- [Templates](./concepts/templates.md)
- [Assets & licensing](./concepts/assets.md)
- [Renders](./concepts/renders.md)
- [Storage & retention](./concepts/storage.md)
- [Environments](./concepts/environments.md)

### Guides
- [Generate a Canvas](./guides/generate-canvas.md)
- [Expand to full-length video](./guides/expand-video.md)
- [Generate multiple variants](./guides/variants.md)
- [Batch generation](./guides/batch-generation.md)
- [Build a template system](./guides/templates.md)
- [Human review & approvals](./guides/review-approvals.md)
- [Export packs](./guides/export-packs.md)
- [Bring your own assets](./guides/byoa.md)
- [Usage-based billing](./guides/billing.md)

### API Reference
- [Tracks](./api/tracks.md)
- [Canvases](./api/canvases.md)
- [Videos](./api/videos.md)
- [Templates](./api/templates.md)
- [Assets](./api/assets.md)
- [Renders](./api/renders.md)
- [Webhooks](./api/webhooks.md)
- [Usage](./api/usage.md)
- [Projects](./api/projects.md)

### Resources
- [SDKs](./resources/sdks.md)
- [Changelog](./resources/changelog.md)
- [Status](./resources/status.md)
- [Security](./resources/security.md)
- [Licensing policy](./resources/licensing.md)
- [Support](./resources/support.md)
