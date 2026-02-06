---
title: LoopCanvas GPU Worker
emoji: 🎬
colorFrom: purple
colorTo: blue
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
hardware: t4-small
---

# LoopCanvas GPU Worker

Generates Spotify Canvas videos at full SDXL + SVD quality on a free T4 GPU.

## Setup

1. Set `LOOPCANVAS_SERVER_URL` in Space secrets
2. The worker connects automatically and starts processing jobs
3. Monitor progress via the Gradio dashboard

## Cost

$0 — runs on HuggingFace Spaces free GPU tier.
