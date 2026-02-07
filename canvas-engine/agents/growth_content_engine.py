#!/usr/bin/env python3
"""
Growth & Community Lead -- Content Engine Agent

Generates SEO content, artist spotlights, community templates, and viral sharing
copy. Runs daily via GitHub Actions. $0 cost -- no paid APIs, no databases.

What it does:
1. ANALYZE: Reads user activity, referral data, and canvas results from JSONL
2. PLAN: Builds a daily content calendar (5-10 pieces across platforms)
3. GENERATE: Produces titles, descriptions, hashtags, SEO meta, templates
4. CONFIGURE: Writes content_config.json + templates/seo_meta.html
5. REPORT: Prints CI-visible content production summary

Content phases (progressive rollout based on content volume):
  - Phase 1 (published <  50): Basic share copy + 5 daily posts
  - Phase 2 (published  50-200): SEO templates + keyword targeting
  - Phase 3 (published 200-500): Community templates (Discord, Twitter)
  - Phase 4 (published > 500): Personalized outreach + artist spotlights

Data: canvas-engine/checklist_data/*.jsonl, canvas-engine/optimization_data/*.jsonl
Config: content_config.json (repo root, read by frontend/CI)
Templates: templates/seo_meta.html (repo root)
Decisions: checklist_data/growth_content_decisions.jsonl
Calendar: checklist_data/content_calendar.jsonl
"""

import json
import hashlib
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field


# ======================================================================
# Paths
# ======================================================================

ENGINE_DIR = Path(__file__).parent.parent
APP_DIR = ENGINE_DIR.parent
DATA_DIR = ENGINE_DIR / "checklist_data"
OPT_DIR = ENGINE_DIR / "optimization_data"
CONFIG_DIR = APP_DIR
TEMPLATE_DIR = APP_DIR / "templates"

DATA_DIR.mkdir(exist_ok=True)
OPT_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)


# ======================================================================
# Data Structures
# ======================================================================

@dataclass
class ContentMetrics:
    """Computed content and community metrics."""
    total_published: int = 0
    total_shares: int = 0
    total_canvases: int = 0
    total_users: int = 0
    avg_quality_score: float = 0.0
    top_directors: List[str] = field(default_factory=list)
    top_genres: List[str] = field(default_factory=list)
    share_by_platform: Dict[str, int] = field(default_factory=dict)
    referral_signups: int = 0
    active_artists: int = 0
    best_canvas_score: float = 0.0
    best_canvas_director: str = ""
    best_canvas_genre: str = ""
    computed_at: str = ""

    def __post_init__(self):
        if not self.computed_at:
            self.computed_at = datetime.now().isoformat()


@dataclass
class ContentDecision:
    """Decisions made by the content engine for this run."""
    phase: int = 1
    daily_target: int = 5
    seo_enabled: bool = False
    community_templates_enabled: bool = False
    personalized_outreach: bool = False
    target_keywords: List[str] = field(default_factory=list)
    platforms: List[str] = field(default_factory=lambda: ["twitter"])
    calendar_items: List[Dict] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


# ======================================================================
# SEO Keyword Bank
# ======================================================================

SEO_KEYWORDS = [
    "Spotify Canvas maker", "Spotify Canvas generator",
    "AI music video maker", "Spotify Canvas from audio",
    "free Spotify Canvas tool", "AI music visualizer",
    "Spotify Canvas creator free", "make Spotify Canvas AI",
    "automatic Spotify Canvas", "loop video music AI",
    "Spotify Canvas tutorial", "AI generated music video",
    "audio reactive video", "cinematic music canvas",
    "AI director music video",
]

HASHTAGS = {
    "twitter": ["#SpotifyCanvas", "#MusicVisuals", "#AIMusic", "#IndieArtist",
                "#MusicProducer", "#SpotifyArtist", "#LoopCanvas", "#MusicVideo",
                "#AIArt", "#MusicCreator"],
    "instagram": ["#SpotifyCanvas", "#MusicVisuals", "#AIMusic", "#IndieMusic",
                  "#MusicProducer", "#SpotifyForArtists", "#LoopCanvas",
                  "#MusicVideoMaker", "#DigitalArt", "#AIGenerated"],
    "tiktok": ["#SpotifyCanvas", "#AIMusic", "#MusicVisuals", "#IndieArtist",
               "#MusicTok", "#SpotifyForArtists", "#LoopCanvas", "#AIArt"],
}

SHARE_COPY_TEMPLATES = [
    "Just turned my track into a cinematic canvas in 30 seconds",
    "My music has a visual identity now. AI did this in seconds.",
    "This AI watched my track and directed a visual story for it",
    "From audio to cinema. The future of music visuals is here.",
    "Every track deserves a visual. Mine just got one automatically.",
    "AI listened to my song and created this. No editing needed.",
    "Upload your track. Get a Spotify Canvas. 30 seconds. Free.",
    "The AI picked up on the emotion in my track. Look at this.",
    "My Spotify Canvas was made by AI. And it actually gets the vibe.",
    "No designers needed. AI turned my beat into a visual masterpiece.",
]

ARTIST_SPOTLIGHT_TEMPLATES = [
    "Artist Spotlight: {artist} turned their {genre} track into a cinematic "
    "canvas. Before: static artwork. After: AI-directed visual story scored "
    "{score}/10. Try it free.",
    "How {artist} got a {score}/10 Spotify Canvas in 30 seconds. Genre: "
    "{genre}. Director: {director}. No design skills needed.",
    "From silence to cinema: {artist} uploaded their {genre} track and "
    "the {director} AI director created a {score}/10 visual in seconds.",
]

DISCORD_WELCOME_TEMPLATE = (
    "Welcome to the LoopCanvas community! Here's how to get started:\n\n"
    "1. Upload your track at loopcanvas.com\n"
    "2. Pick a director (or let the AI choose)\n"
    "3. Export your Spotify Canvas in 30 seconds\n\n"
    "Share your creations in #showcase and get feedback from fellow artists.\n\n"
    "Current stats:\n- {canvas_count} canvases created\n"
    "- {artist_count} active artists\n- Average quality: {avg_score}/10\n\n"
    "Need help? Ask in #support. We're all here to make better visuals.")

TWITTER_REPLY_TEMPLATES = [
    "Have you tried LoopCanvas? Upload your track and get a Spotify Canvas "
    "in 30 seconds. Free for 3/month.",
    "The AI actually listens to your track and picks a visual style that "
    "matches. It's wild. Try loopcanvas.com",
    "I've been using this for my Spotify Canvases. The AI director thing "
    "is actually good. loopcanvas.com",
]

WATERMARK_COPY_VARIANTS = [
    "Made with LoopCanvas", "Created by LoopCanvas AI",
    "LoopCanvas.com", "Visuals by LoopCanvas",
]


# ======================================================================
# Core Agent
# ======================================================================

class GrowthContentEngine:
    """Autonomous content generation and community building agent."""

    def __init__(self):
        self.metrics = ContentMetrics()
        self.decision = ContentDecision()
        self.config_file = CONFIG_DIR / "content_config.json"
        self.seo_template_file = TEMPLATE_DIR / "seo_meta.html"
        self.calendar_file = DATA_DIR / "content_calendar.jsonl"
        self.decisions_file = DATA_DIR / "growth_content_decisions.jsonl"
        self._raw_activity: List[Dict] = []
        self._raw_referral: List[Dict] = []
        self._raw_canvas: List[Dict] = []
        self._raw_calendar: List[Dict] = []

    # ==================================================================
    # Step 1: ANALYZE
    # ==================================================================

    def analyze(self) -> ContentMetrics:
        print("\n" + "=" * 60)
        print("GROWTH CONTENT ENGINE -- ANALYZE")
        print("=" * 60)
        self._load_data()
        self._compute_canvas_stats()
        self._compute_share_stats()
        self._compute_user_stats()
        self._compute_content_volume()
        return self.metrics

    def _load_data(self):
        self._raw_activity = self._read_jsonl(DATA_DIR / "user_activity.jsonl")
        self._raw_referral = self._read_jsonl(DATA_DIR / "referral_data.jsonl")
        self._raw_canvas = self._read_jsonl(OPT_DIR / "canvas_results.jsonl")
        self._raw_calendar = self._read_jsonl(self.calendar_file)
        print("  Loaded: {} activity, {} referral, {} canvas, {} calendar".format(
            len(self._raw_activity), len(self._raw_referral),
            len(self._raw_canvas), len(self._raw_calendar)))

    def _read_jsonl(self, path: Path) -> List[Dict]:
        if not path.exists():
            return []
        records = []
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
        return records

    def _compute_canvas_stats(self):
        if not self._raw_canvas:
            print("  canvas_stats: no data")
            return
        self.metrics.total_canvases = len(self._raw_canvas)
        scores = [r.get("quality_score", 0.0) for r in self._raw_canvas if r.get("quality_score")]
        self.metrics.avg_quality_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        director_counts: Dict[str, int] = {}
        genre_counts: Dict[str, int] = {}
        best_score, best_director, best_genre = 0.0, "", ""
        for r in self._raw_canvas:
            director = r.get("director", r.get("style", ""))
            genre = r.get("genre", "")
            score = r.get("quality_score", 0.0)
            if director:
                director_counts[director] = director_counts.get(director, 0) + 1
            if genre:
                genre_counts[genre] = genre_counts.get(genre, 0) + 1
            if score > best_score:
                best_score, best_director, best_genre = score, director, genre
        self.metrics.top_directors = sorted(director_counts, key=director_counts.get, reverse=True)[:5]
        self.metrics.top_genres = sorted(genre_counts, key=genre_counts.get, reverse=True)[:5]
        self.metrics.best_canvas_score = best_score
        self.metrics.best_canvas_director = best_director
        self.metrics.best_canvas_genre = best_genre
        print("  canvases: {} total, avg quality {:.2f}/10".format(
            self.metrics.total_canvases, self.metrics.avg_quality_score))

    def _compute_share_stats(self):
        if not self._raw_referral:
            print("  share_stats: no data")
            return
        platform_counts: Dict[str, int] = {}
        total_shares, total_signups = 0, 0
        for r in self._raw_referral:
            action = r.get("action", "")
            if action == "share":
                total_shares += 1
                p = r.get("platform", "unknown")
                platform_counts[p] = platform_counts.get(p, 0) + 1
            elif action == "signup_from_share":
                total_signups += 1
        self.metrics.total_shares = total_shares
        self.metrics.share_by_platform = platform_counts
        self.metrics.referral_signups = total_signups
        print("  shares: {} total, signups: {}".format(total_shares, total_signups))

    def _compute_user_stats(self):
        sessions = set()
        for event in self._raw_activity:
            sid = event.get("session_id", event.get("user_id", ""))
            if sid:
                sessions.add(sid)
        self.metrics.total_users = len(sessions)
        self.metrics.active_artists = len(sessions)
        print("  active users: {}".format(self.metrics.total_users))

    def _compute_content_volume(self):
        self.metrics.total_published = len(self._raw_calendar)
        print("  published content items: {}".format(self.metrics.total_published))

    # ==================================================================
    # Step 2: DECIDE
    # ==================================================================

    def decide(self) -> ContentDecision:
        print("\n" + "=" * 60)
        print("GROWTH CONTENT ENGINE -- DECIDE")
        print("=" * 60)
        published = self.metrics.total_published
        if published < 50:
            self._decide_phase1()
        elif published < 200:
            self._decide_phase2()
        elif published < 500:
            self._decide_phase3()
        else:
            self._decide_phase4()
        self._build_content_calendar()
        self._add_recommendations()
        print("  Phase: {}  Daily: {}  SEO: {}  Community: {}  Outreach: {}".format(
            self.decision.phase, self.decision.daily_target,
            "ON" if self.decision.seo_enabled else "OFF",
            "ON" if self.decision.community_templates_enabled else "OFF",
            "ON" if self.decision.personalized_outreach else "OFF"))
        print("  Calendar items: {}".format(len(self.decision.calendar_items)))
        return self.decision

    def _decide_phase1(self):
        self.decision.phase = 1
        self.decision.daily_target = 5
        self.decision.seo_enabled = False
        self.decision.community_templates_enabled = False
        self.decision.personalized_outreach = False
        self.decision.target_keywords = SEO_KEYWORDS[:3]
        self.decision.platforms = ["twitter"]
        self.decision.recommendations.append(
            "Phase 1: Basic share copy active. Producing 5 posts/day to build initial content volume.")

    def _decide_phase2(self):
        self.decision.phase = 2
        self.decision.daily_target = 7
        self.decision.seo_enabled = True
        self.decision.community_templates_enabled = False
        self.decision.personalized_outreach = False
        self.decision.target_keywords = SEO_KEYWORDS[:8]
        self.decision.platforms = ["twitter", "instagram"]
        self.decision.recommendations.append(
            "Phase 2: SEO templates enabled. Targeting top 8 keywords to dominate 'Spotify Canvas maker' searches.")

    def _decide_phase3(self):
        self.decision.phase = 3
        self.decision.daily_target = 8
        self.decision.seo_enabled = True
        self.decision.community_templates_enabled = True
        self.decision.personalized_outreach = False
        self.decision.target_keywords = SEO_KEYWORDS[:12]
        self.decision.platforms = ["twitter", "instagram", "tiktok"]
        self.decision.recommendations.append(
            "Phase 3: Community templates active. Discord welcome messages and Twitter reply templates deployed.")

    def _decide_phase4(self):
        self.decision.phase = 4
        self.decision.daily_target = 10
        self.decision.seo_enabled = True
        self.decision.community_templates_enabled = True
        self.decision.personalized_outreach = True
        self.decision.target_keywords = SEO_KEYWORDS
        self.decision.platforms = ["twitter", "instagram", "tiktok", "discord"]
        self.decision.recommendations.append(
            "Phase 4: Personalized outreach enabled. Artist spotlights and genre-targeted content active.")

    def _build_content_calendar(self):
        today = datetime.now().strftime("%Y-%m-%d")
        items = []
        for i in range(min(self.decision.daily_target, len(SHARE_COPY_TEMPLATES))):
            seed = hashlib.md5((today + str(i)).encode()).hexdigest()[:8]
            idx = int(seed, 16) % len(SHARE_COPY_TEMPLATES)
            copy_text = SHARE_COPY_TEMPLATES[idx]
            platform = self.decision.platforms[i % len(self.decision.platforms)]
            tags = HASHTAGS.get(platform, HASHTAGS["twitter"])
            tag_start = int(seed, 16) % max(len(tags) - 4, 1)
            selected_tags = tags[tag_start:tag_start + 4]
            items.append({"date": today, "index": i, "platform": platform,
                          "type": "share_copy", "title": copy_text[:60],
                          "description": copy_text, "hashtags": selected_tags,
                          "status": "generated", "seed": seed})
        if self.decision.personalized_outreach and self.metrics.best_canvas_score > 0:
            spotlight = ARTIST_SPOTLIGHT_TEMPLATES[0].format(
                artist="Featured Artist", genre=self.metrics.best_canvas_genre or "electronic",
                director=self.metrics.best_canvas_director or "AI Director",
                score="{:.1f}".format(self.metrics.best_canvas_score))
            items.append({"date": today, "index": len(items), "platform": "twitter",
                          "type": "artist_spotlight", "title": "Artist Spotlight",
                          "description": spotlight, "hashtags": ["#ArtistSpotlight", "#SpotifyCanvas", "#LoopCanvas"],
                          "status": "generated", "seed": ""})
        if self.decision.seo_enabled:
            primary_kw = self.decision.target_keywords[0] if self.decision.target_keywords else "Spotify Canvas maker"
            items.append({"date": today, "index": len(items), "platform": "seo", "type": "seo_meta",
                          "title": "{} - Free AI Tool | LoopCanvas".format(primary_kw),
                          "description": "Create stunning {} results with LoopCanvas.".format(primary_kw.lower()),
                          "hashtags": [], "status": "generated", "seed": ""})
        self.decision.calendar_items = items

    def _add_recommendations(self):
        if self.metrics.total_shares == 0 and self.metrics.total_canvases > 0:
            self.decision.recommendations.append(
                "Zero shares detected. Priority: optimize share prompt copy and placement in the export flow.")
        if self.metrics.total_shares > 0 and self.metrics.referral_signups == 0:
            self.decision.recommendations.append(
                "Shares happening but zero referral signups. Optimize share link landing page and OG tags.")
        if 0 < self.metrics.avg_quality_score < 7.0:
            self.decision.recommendations.append(
                "Avg quality {:.1f}/10 is below 7.0 threshold. Hold off on spotlight content.".format(
                    self.metrics.avg_quality_score))
        if self.metrics.top_genres:
            self.decision.recommendations.append(
                "Top genres: {}. Target content to these genres first.".format(
                    ", ".join(self.metrics.top_genres[:3])))

    # ==================================================================
    # Step 3: WRITE CONFIG
    # ==================================================================

    def write_config(self):
        print("\n" + "=" * 60)
        print("GROWTH CONTENT ENGINE -- WRITE CONFIG")
        print("=" * 60)
        version = 1
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    existing = json.load(f)
                version = existing.get("version", 0) + 1
            except (json.JSONDecodeError, OSError):
                pass
        config = {
            "version": version, "updated_at": datetime.now().isoformat(),
            "phase": self.decision.phase, "daily_target": self.decision.daily_target,
            "seo": {"enabled": self.decision.seo_enabled, "target_keywords": self.decision.target_keywords,
                    "primary_keyword": self.decision.target_keywords[0] if self.decision.target_keywords else ""},
            "community": {"templates_enabled": self.decision.community_templates_enabled,
                          "discord_welcome": DISCORD_WELCOME_TEMPLATE.format(
                              canvas_count=self.metrics.total_canvases, artist_count=self.metrics.active_artists,
                              avg_score="{:.1f}".format(self.metrics.avg_quality_score)),
                          "twitter_reply_templates": TWITTER_REPLY_TEMPLATES if self.decision.community_templates_enabled else []},
            "outreach": {"personalized": self.decision.personalized_outreach,
                         "spotlight_templates": ARTIST_SPOTLIGHT_TEMPLATES if self.decision.personalized_outreach else []},
            "sharing": {"platforms": self.decision.platforms, "copy_variants": SHARE_COPY_TEMPLATES[:5],
                        "watermark_copy": WATERMARK_COPY_VARIANTS,
                        "hashtags": {p: HASHTAGS.get(p, []) for p in self.decision.platforms}},
            "metrics": {"total_published": self.metrics.total_published, "total_canvases": self.metrics.total_canvases,
                        "total_shares": self.metrics.total_shares, "active_artists": self.metrics.active_artists,
                        "avg_quality": self.metrics.avg_quality_score, "top_directors": self.metrics.top_directors[:3],
                        "top_genres": self.metrics.top_genres[:3]},
            "recommendations": self.decision.recommendations}
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            print("  Written: {}".format(self.config_file))
        except OSError as e:
            print("  [error] Failed to write config: {}".format(e))

    # ==================================================================
    # Step 4: WRITE TEMPLATES
    # ==================================================================

    def write_templates(self):
        print("\n" + "=" * 60)
        print("GROWTH CONTENT ENGINE -- WRITE TEMPLATES")
        print("=" * 60)
        self._write_seo_meta_template()
        self._write_content_calendar()

    def _write_seo_meta_template(self):
        if not self.decision.seo_enabled:
            print("  [skip] SEO not enabled in current phase")
            return
        primary_kw = self.decision.target_keywords[0] if self.decision.target_keywords else "Spotify Canvas maker"
        all_kw = ", ".join(self.decision.target_keywords[:10])
        ds = datetime.now().strftime('%Y%m%d')
        structured_data = json.dumps({"@context": "https://schema.org", "@type": "WebApplication",
            "name": "LoopCanvas", "url": "https://loopcanvas.com",
            "description": "AI-powered Spotify Canvas maker. Upload your track, get a cinematic loop video in 30 seconds.",
            "applicationCategory": "MultimediaApplication", "operatingSystem": "Web",
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD",
                       "description": "Free tier: 3 canvases per month"}}, indent=2)
        html = ('<!-- SEO Meta -- Auto-generated by Growth Content Engine v' + ds + ' -->\n'
                '<title>' + primary_kw + ' - Free AI Tool | LoopCanvas</title>\n'
                '<meta name="title" content="' + primary_kw + ' - Free AI Tool | LoopCanvas" />\n'
                '<meta name="description" content="Create stunning Spotify Canvases with AI. Upload your track, choose a cinematic director, export in 30 seconds. Free for 3 canvases/month." />\n'
                '<meta name="keywords" content="' + all_kw + '" />\n'
                '<meta name="robots" content="index, follow" />\n'
                '<link rel="canonical" href="https://loopcanvas.com" />\n'
                '<meta property="og:type" content="website" />\n'
                '<meta property="og:url" content="https://loopcanvas.com" />\n'
                '<meta property="og:title" content="' + primary_kw + ' - Free AI Tool | LoopCanvas" />\n'
                '<meta property="og:description" content="Upload your track. AI directs a cinematic Spotify Canvas in 30 seconds. Free." />\n'
                '<meta property="og:image" content="https://loopcanvas.com/assets/og-image.png" />\n'
                '<meta property="twitter:card" content="summary_large_image" />\n'
                '<meta property="twitter:title" content="' + primary_kw + ' - LoopCanvas" />\n'
                '<meta property="twitter:description" content="AI-directed Spotify Canvases from your audio. 30 seconds. Free." />\n'
                '<meta property="twitter:image" content="https://loopcanvas.com/assets/og-image.png" />\n'
                '<script type="application/ld+json">\n' + structured_data + '\n</script>\n')
        try:
            with open(self.seo_template_file, 'w') as f:
                f.write(html)
            print("  Written: {}".format(self.seo_template_file))
        except OSError as e:
            print("  [error] seo_meta.html: {}".format(e))

    def _write_content_calendar(self):
        if not self.decision.calendar_items:
            print("  [skip] No calendar items to write")
            return
        try:
            with open(self.calendar_file, 'a') as f:
                for item in self.decision.calendar_items:
                    f.write(json.dumps(item) + "\n")
            print("  Appended {} items to {}".format(len(self.decision.calendar_items), self.calendar_file))
        except OSError as e:
            print("  [error] content_calendar.jsonl: {}".format(e))

    def _log_decision(self):
        record = {"timestamp": datetime.now().isoformat(), "phase": self.decision.phase,
                  "daily_target": self.decision.daily_target, "seo_enabled": self.decision.seo_enabled,
                  "community_templates": self.decision.community_templates_enabled,
                  "personalized_outreach": self.decision.personalized_outreach,
                  "calendar_items_count": len(self.decision.calendar_items),
                  "metrics": {"total_published": self.metrics.total_published,
                              "total_canvases": self.metrics.total_canvases,
                              "total_shares": self.metrics.total_shares,
                              "active_artists": self.metrics.active_artists,
                              "avg_quality": self.metrics.avg_quality_score},
                  "recommendations": self.decision.recommendations}
        try:
            with open(self.decisions_file, 'a') as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            pass

    # ==================================================================
    # Step 5: RUN
    # ==================================================================

    def run(self):
        start = datetime.now()
        print("\n" + "#" * 60)
        print("# GROWTH CONTENT ENGINE -- " + start.strftime('%Y-%m-%d %H:%M:%S'))
        print("# Target: 5-10 content pieces daily  |  Cost: $0")
        print("#" * 60)
        self.analyze()
        self.decide()
        self.write_config()
        self.write_templates()
        self._log_decision()
        elapsed = (datetime.now() - start).total_seconds()
        self._print_report(elapsed)

    def _print_report(self, elapsed=0.0):
        print("\n" + "=" * 60)
        print("GROWTH CONTENT ENGINE -- REPORT")
        print("=" * 60)
        for name, value, target, unit in [("total_published", self.metrics.total_published, 500, ""),
                                           ("total_canvases", self.metrics.total_canvases, 1000, ""),
                                           ("total_shares", self.metrics.total_shares, 100, ""),
                                           ("active_artists", self.metrics.active_artists, 50, ""),
                                           ("avg_quality", self.metrics.avg_quality_score, 9.3, "/10")]:
            status = "PASS" if value >= target else "BELOW"
            ratio = value / target if target > 0 else 0
            bar_len = int(min(ratio, 1.0) * 20)
            bar = "#" * bar_len + "-" * (20 - bar_len)
            print("  {:20s} {:>8}{} / {}{} [{}]  {}".format(name, value, unit, target, unit, bar, status))
        print("\n  Phase: {}  Calendar: {}  SEO keywords: {}".format(
            self.decision.phase, len(self.decision.calendar_items), len(self.decision.target_keywords)))
        if self.decision.recommendations:
            print("\n  Recommendations:")
            for i, rec in enumerate(self.decision.recommendations, 1):
                print("    {}. {}".format(i, rec))
        if elapsed > 0:
            print("\n  Runtime: {:.1f}s".format(elapsed))
        print("=" * 60 + "\n")

    def report(self):
        if not self.config_file.exists():
            print("No content_config.json found. Run the agent first.")
            return
        try:
            with open(self.config_file) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print("Error reading config: {}".format(e))
            return
        print("\n" + "=" * 60)
        print("GROWTH CONTENT ENGINE -- LATEST REPORT")
        print("=" * 60)
        print("  Version: {}  Updated: {}  Phase: {}".format(
            config.get("version", "?"), config.get("updated_at", "?"), config.get("phase", "?")))
        for k, v in config.get("metrics", {}).items():
            print("    {}: {}".format(k, v))
        recs = config.get("recommendations", [])
        if recs:
            print("\n  Recommendations:")
            for i, rec in enumerate(recs, 1):
                print("    {}. {}".format(i, rec))
        print("=" * 60 + "\n")


# ======================================================================
# Singleton
# ======================================================================

_agent: Optional[GrowthContentEngine] = None


def get_growth_content_engine() -> GrowthContentEngine:
    global _agent
    if _agent is None:
        _agent = GrowthContentEngine()
    return _agent


# ======================================================================
# CLI
# ======================================================================

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    agent = GrowthContentEngine()
    if cmd == "report":
        agent.report()
    elif cmd == "run":
        agent.run()
    else:
        print("Usage: python -m agents.growth_content_engine [run|report]")
        sys.exit(1)
