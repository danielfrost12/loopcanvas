#!/usr/bin/env python3
"""
Canvas Director Philosophy Engine (Patent-Ready Innovation #2)

"Not just WHAT a director does, but WHY they do it."

This is the soul of Canvas. Every great director has a visual philosophy:
- Spike Jonze: Beauty in vulnerability, mundane made magical
- Hype Williams: Mythological grandeur, the mundane made legendary
- Dave Meyers: Kinetic energy, controlled chaos
- The Daniels: Absurdist emotion, surreal sincerity
- Khalil Joseph: Poetic intimacy, cultural texture
- Wong Kar-wai: Romantic longing, time as emotion

The system doesn't just copy their style - it understands their philosophy
and applies it to new creative decisions.

$0 cost - uses LoRA adapters trained on Google Colab
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import json


class DirectorStyle(Enum):
    """Available director styles"""
    SPIKE_JONZE = "spike_jonze"
    HYPE_WILLIAMS = "hype_williams"
    DAVE_MEYERS = "dave_meyers"
    THE_DANIELS = "the_daniels"
    KHALIL_JOSEPH = "khalil_joseph"
    WONG_KAR_WAI = "wong_kar_wai"
    # Canvas originals
    OBSERVED_MOMENT = "observed_moment"
    GOLDEN_HOUR = "golden_hour"
    MIDNIGHT_DRIFT = "midnight_drift"


@dataclass
class DirectorPhilosophy:
    """The creative philosophy of a director"""
    name: str
    style_id: str

    # Core philosophy
    central_theme: str  # What they're always exploring
    emotional_approach: str  # How they handle emotion
    visual_metaphor_style: str  # How they use visual metaphor

    # Visual preferences
    color_philosophy: Dict[str, any]  # How they use color
    lighting_approach: str  # Their lighting philosophy
    camera_movement: str  # How they move the camera
    editing_rhythm: str  # Their editing style
    texture_preference: str  # Film vs digital, grain, etc.

    # Emotional mapping
    emotion_to_visual: Dict[str, Dict]  # How they visualize emotions

    # LoRA parameters (for generation)
    lora_strength: float = 0.75
    lora_path: Optional[str] = None

    # Generation parameters
    default_params: Dict = field(default_factory=dict)


class DirectorPhilosophyEngine:
    """
    The Director Philosophy Engine

    Understands WHY directors make visual choices, not just WHAT they do.
    Maps emotional DNA from audio to directorial vision.
    """

    def __init__(self):
        self.directors = self._initialize_directors()

    def _initialize_directors(self) -> Dict[str, DirectorPhilosophy]:
        """Initialize all director philosophies"""

        return {
            DirectorStyle.SPIKE_JONZE.value: DirectorPhilosophy(
                name="Spike Jonze",
                style_id="spike_jonze",
                central_theme="Finding beauty in vulnerability and the absurdity of being human",
                emotional_approach="Sincere without being sentimental. Lets awkwardness be beautiful.",
                visual_metaphor_style="Literal fantasies that reveal emotional truths",
                color_philosophy={
                    "palette": "Muted naturals with sudden pops of meaning",
                    "temperature": "Warm but not golden - lived-in warmth",
                    "saturation": 0.65,  # Slightly desaturated
                    "contrast": 0.70,
                },
                lighting_approach="Natural light, often overcast. Finds beauty in flat light.",
                camera_movement="Observational, curious. Camera as a friend watching.",
                editing_rhythm="Patient, lets moments breathe. Cuts on emotion, not action.",
                texture_preference="Film grain, slight softness. Never clinical.",
                emotion_to_visual={
                    "sadness": {
                        "approach": "Find the beauty in it, don't wallow",
                        "colors": ["muted blue", "soft grey", "warm skin tones"],
                        "motion": "slow, deliberate",
                        "lighting": "overcast, gentle",
                    },
                    "joy": {
                        "approach": "Childlike wonder, genuine surprise",
                        "colors": ["bright but not garish", "natural greens", "sky blue"],
                        "motion": "playful, curious",
                        "lighting": "golden hour, dappled",
                    },
                    "longing": {
                        "approach": "Physical distance as emotional distance",
                        "colors": ["desaturated", "memory-like"],
                        "motion": "reaching, searching",
                        "lighting": "backlit, silhouette",
                    },
                },
                default_params={
                    "grain": 0.15,
                    "blur": 0.8,
                    "contrast": 0.70,
                    "saturation": 0.65,
                    "motion_intensity": 0.4,
                }
            ),

            DirectorStyle.HYPE_WILLIAMS.value: DirectorPhilosophy(
                name="Hype Williams",
                style_id="hype_williams",
                central_theme="Making the everyday feel mythological and legendary",
                emotional_approach="Confident, unapologetic. Emotion as power.",
                visual_metaphor_style="Symbolic imagery that elevates the subject to icon status",
                color_philosophy={
                    "palette": "High contrast, bold primaries, gold as divine",
                    "temperature": "Warm golds and cool blues in contrast",
                    "saturation": 0.85,
                    "contrast": 0.90,
                },
                lighting_approach="Dramatic, theatrical. Light as sculpture.",
                camera_movement="Slow, reverent. Subjects are monuments.",
                editing_rhythm="Slower cuts, held shots. Let the image imprint.",
                texture_preference="Clean but rich. Digital clarity with film color.",
                emotion_to_visual={
                    "power": {
                        "approach": "The subject becomes a god",
                        "colors": ["gold", "deep red", "black"],
                        "motion": "slow, commanding",
                        "lighting": "dramatic uplighting, rim light",
                    },
                    "desire": {
                        "approach": "Sensual without being explicit",
                        "colors": ["deep red", "gold", "shadow"],
                        "motion": "slow motion, lingering",
                        "lighting": "warm, soft shadows",
                    },
                    "triumph": {
                        "approach": "Victory lap, coronation",
                        "colors": ["gold", "white", "blue sky"],
                        "motion": "ascending, expansive",
                        "lighting": "heroic backlight, sun flares",
                    },
                },
                default_params={
                    "grain": 0.05,
                    "blur": 0.3,
                    "contrast": 0.90,
                    "saturation": 0.85,
                    "motion_intensity": 0.3,
                }
            ),

            DirectorStyle.DAVE_MEYERS.value: DirectorPhilosophy(
                name="Dave Meyers",
                style_id="dave_meyers",
                central_theme="Controlled chaos, kinetic energy, visual maximalism",
                emotional_approach="Explosive, unapologetic. Energy as emotion.",
                visual_metaphor_style="Surreal set pieces that externalize internal states",
                color_philosophy={
                    "palette": "Bold, saturated, often surreal color combinations",
                    "temperature": "Varies dramatically within same piece",
                    "saturation": 0.95,
                    "contrast": 0.85,
                },
                lighting_approach="Theatrical, production-heavy. Light as spectacle.",
                camera_movement="Dynamic, athletic. Camera is a participant.",
                editing_rhythm="Fast, rhythmic. Cuts on the beat, often faster.",
                texture_preference="Clean, high production value. Every frame is composed.",
                emotion_to_visual={
                    "energy": {
                        "approach": "Movement is meaning",
                        "colors": ["electric", "neon", "saturated"],
                        "motion": "fast, athletic, surprising",
                        "lighting": "dynamic, colored, moving",
                    },
                    "confidence": {
                        "approach": "Spectacle as self-expression",
                        "colors": ["bold", "fashion-forward"],
                        "motion": "choreographed, precise",
                        "lighting": "flattering, production-quality",
                    },
                    "transformation": {
                        "approach": "Visual metamorphosis",
                        "colors": ["shifting", "transitional"],
                        "motion": "morphing, revealing",
                        "lighting": "dramatic reveals",
                    },
                },
                default_params={
                    "grain": 0.02,
                    "blur": 0.2,
                    "contrast": 0.85,
                    "saturation": 0.95,
                    "motion_intensity": 0.8,
                }
            ),

            DirectorStyle.KHALIL_JOSEPH.value: DirectorPhilosophy(
                name="Khalil Joseph",
                style_id="khalil_joseph",
                central_theme="Poetic intimacy, cultural texture, time as non-linear",
                emotional_approach="Impressionistic. Emotion through accumulation.",
                visual_metaphor_style="Documentary intimacy mixed with dreamlike sequences",
                color_philosophy={
                    "palette": "Rich, warm, rooted in Black visual culture",
                    "temperature": "Warm, golden, earthy",
                    "saturation": 0.70,
                    "contrast": 0.65,
                },
                lighting_approach="Natural, intimate. Often golden hour or practical lights.",
                camera_movement="Handheld intimacy, observational but personal.",
                editing_rhythm="Poetic, non-linear. Time folds on itself.",
                texture_preference="Heavy film grain, Super 8 mixed with 35mm. Texture is memory.",
                emotion_to_visual={
                    "memory": {
                        "approach": "Time is not linear, memory bleeds",
                        "colors": ["warm", "sepia-adjacent", "golden"],
                        "motion": "slow motion, time manipulation",
                        "lighting": "golden hour, practical lights",
                    },
                    "community": {
                        "approach": "Collective experience, shared space",
                        "colors": ["warm skin tones", "earth tones"],
                        "motion": "intimate, observational",
                        "lighting": "natural, lived-in",
                    },
                    "transcendence": {
                        "approach": "The spiritual in the everyday",
                        "colors": ["golden", "ethereal", "light-filled"],
                        "motion": "ascending, floating",
                        "lighting": "backlit, divine light",
                    },
                },
                default_params={
                    "grain": 0.25,
                    "blur": 1.0,
                    "contrast": 0.65,
                    "saturation": 0.70,
                    "motion_intensity": 0.45,
                }
            ),

            DirectorStyle.WONG_KAR_WAI.value: DirectorPhilosophy(
                name="Wong Kar-wai",
                style_id="wong_kar_wai",
                central_theme="Romantic longing, missed connections, time as emotion",
                emotional_approach="Melancholic beauty. Longing is the point.",
                visual_metaphor_style="Urban isolation, reflections, frames within frames",
                color_philosophy={
                    "palette": "Saturated but moody - neon against shadow",
                    "temperature": "Cool blues and greens with warm accent lights",
                    "saturation": 0.75,
                    "contrast": 0.80,
                },
                lighting_approach="Neon, practical lights, shadow and revelation.",
                camera_movement="Slow motion as emotional emphasis. Frames that trap.",
                editing_rhythm="Step-printing, speed changes. Time stretches.",
                texture_preference="Film grain, step-printing blur, color pushed in processing.",
                emotion_to_visual={
                    "longing": {
                        "approach": "Distance despite proximity",
                        "colors": ["neon", "shadow", "reflection"],
                        "motion": "slow motion, step-printed",
                        "lighting": "neon, rain-slicked, isolated pools",
                    },
                    "nostalgia": {
                        "approach": "The past is always beautiful and unreachable",
                        "colors": ["warm", "faded", "golden"],
                        "motion": "slow, repetitive",
                        "lighting": "practical, warm, intimate",
                    },
                    "urban_isolation": {
                        "approach": "Alone in a crowd",
                        "colors": ["neon", "cold", "clinical"],
                        "motion": "everyone else is fast, subject is slow",
                        "lighting": "harsh, fluorescent, unforgiving",
                    },
                },
                default_params={
                    "grain": 0.18,
                    "blur": 1.2,
                    "contrast": 0.80,
                    "saturation": 0.75,
                    "motion_intensity": 0.35,
                }
            ),

            DirectorStyle.THE_DANIELS.value: DirectorPhilosophy(
                name="The Daniels",
                style_id="the_daniels",
                central_theme="Absurdist emotion, surreal sincerity, multiverse of feeling",
                emotional_approach="Earnest despite the absurd. Comedy and tragedy coexist.",
                visual_metaphor_style="Literal visualization of internal chaos",
                color_philosophy={
                    "palette": "Varies wildly - emotional state dictates palette",
                    "temperature": "Shifts with emotion",
                    "saturation": 0.80,
                    "contrast": 0.75,
                },
                lighting_approach="Varies - can be naturalistic or theatrical within same piece.",
                camera_movement="Often static wide shots, then sudden kinetic bursts.",
                editing_rhythm="Unexpected. Long holds broken by rapid cutting.",
                texture_preference="Clean when absurd, grainy when intimate.",
                emotion_to_visual={
                    "chaos": {
                        "approach": "Visual overload as emotional truth",
                        "colors": ["everything", "clashing", "overwhelming"],
                        "motion": "frenetic, impossible",
                        "lighting": "varies rapidly",
                    },
                    "sincerity": {
                        "approach": "Stillness after the storm",
                        "colors": ["muted", "warm", "grounded"],
                        "motion": "slow, deliberate",
                        "lighting": "natural, soft",
                    },
                    "wonder": {
                        "approach": "The mundane becomes magical",
                        "colors": ["heightened reality", "slightly surreal"],
                        "motion": "floating, discovering",
                        "lighting": "magical realism",
                    },
                },
                default_params={
                    "grain": 0.10,
                    "blur": 0.5,
                    "contrast": 0.75,
                    "saturation": 0.80,
                    "motion_intensity": 0.6,
                }
            ),

            # Canvas Original Styles
            DirectorStyle.OBSERVED_MOMENT.value: DirectorPhilosophy(
                name="Observed Moment",
                style_id="observed_moment",
                central_theme="Footage that doesn't know it's being watched",
                emotional_approach="Intimate distance. Present but not intrusive.",
                visual_metaphor_style="Found footage aesthetic, peripheral glimpses",
                color_philosophy={
                    "palette": "Muted, lifted shadows, no pure black",
                    "temperature": "Warm but restrained",
                    "saturation": 0.75,
                    "contrast": 0.80,
                },
                lighting_approach="Natural, available light only. Never staged.",
                camera_movement="Handheld, observational, never drawing attention.",
                editing_rhythm="Patient. Moments breathe.",
                texture_preference="Heavy film grain, soft focus, vintage texture.",
                emotion_to_visual={
                    "nostalgia": {
                        "approach": "Memory texture, edges dissolving",
                        "colors": ["warm", "amber", "cream"],
                        "motion": "gentle drift, breathing light",
                        "lighting": "golden, natural",
                    },
                    "intimacy": {
                        "approach": "Close but not intrusive",
                        "colors": ["skin tones", "warm shadows"],
                        "motion": "slow, deliberate",
                        "lighting": "practical, warm",
                    },
                    "melancholy": {
                        "approach": "Beautiful sadness, not depression",
                        "colors": ["muted", "cool undertones", "lifted blacks"],
                        "motion": "slow drift, breathing",
                        "lighting": "overcast, soft",
                    },
                },
                default_params={
                    "grain": 0.18,
                    "blur": 1.2,
                    "contrast": 0.80,
                    "saturation": 0.75,
                    "motion_intensity": 0.4,
                }
            ),
        }

    def get_director(self, style: str) -> Optional[DirectorPhilosophy]:
        """Get a director's philosophy by style ID"""
        return self.directors.get(style)

    def match_audio_to_director(self, emotional_dna: dict) -> Tuple[str, float]:
        """
        Match audio emotional DNA to the best director style.

        Returns: (director_style_id, confidence_score)
        """
        valence = emotional_dna.get('valence', 0)
        arousal = emotional_dna.get('arousal', 0.5)
        dominance = emotional_dna.get('dominance', 0.5)
        genre = emotional_dna.get('genre_predictions', {})

        # Scoring for each director
        scores = {}

        # Spike Jonze: Vulnerable, moderate energy, indie/alternative
        scores['spike_jonze'] = (
            0.3 * (1 - abs(valence))  # Prefers emotional complexity
            + 0.3 * (1 - arousal)  # Prefers lower energy
            + 0.2 * genre.get('indie', 0)
            + 0.2 * (1 - dominance)  # Vulnerability
        )

        # Hype Williams: Confident, powerful, hip-hop
        scores['hype_williams'] = (
            0.3 * dominance
            + 0.2 * (1 - arousal) * 0.5  # Slow but powerful
            + 0.3 * genre.get('hip_hop', 0)
            + 0.2 * max(valence, 0)  # Positive or neutral
        )

        # Dave Meyers: High energy, pop/electronic
        scores['dave_meyers'] = (
            0.4 * arousal
            + 0.3 * genre.get('pop', 0)
            + 0.2 * genre.get('electronic', 0)
            + 0.1 * dominance
        )

        # Khalil Joseph: R&B, soulful, warm
        scores['khalil_joseph'] = (
            0.3 * genre.get('r_and_b', 0)
            + 0.3 * (0.5 - abs(valence - 0.2))  # Slight melancholy
            + 0.2 * (1 - arousal)
            + 0.2 * (emotional_dna.get('warmth', 0.5))
        )

        # Wong Kar-wai: Longing, urban, moderate energy
        scores['wong_kar_wai'] = (
            0.4 * (1 - valence) if valence < 0 else 0.2  # Prefers melancholy
            + 0.3 * (0.5 - abs(arousal - 0.4))  # Moderate energy
            + 0.2 * genre.get('electronic', 0)
            + 0.1 * genre.get('r_and_b', 0)
        )

        # The Daniels: Chaotic energy, genre-mixing
        scores['the_daniels'] = (
            0.3 * arousal
            + 0.3 * abs(valence)  # Emotional extremes
            + 0.2 * (1 - max(genre.values()) if genre else 0.5)  # Genre ambiguity
            + 0.2 * emotional_dna.get('rhythm_complexity', 0.5)
        )

        # Observed Moment: Universal, works for everything
        scores['observed_moment'] = (
            0.25 * (1 - arousal)  # Calmer
            + 0.25 * (0.5 - abs(valence))  # Emotionally complex
            + 0.25 * emotional_dna.get('warmth', 0.5)
            + 0.25 * 0.7  # Base score - works for most
        )

        # Find best match
        best_director = max(scores, key=scores.get)
        confidence = scores[best_director]

        return best_director, min(confidence, 1.0)

    def get_generation_params(self, style: str, emotion: str = None) -> dict:
        """
        Get generation parameters for a director style.

        Args:
            style: Director style ID
            emotion: Specific emotion to target (optional)

        Returns:
            Dict of generation parameters
        """
        director = self.get_director(style)
        if not director:
            director = self.get_director('observed_moment')

        params = director.default_params.copy()

        # Add emotion-specific overrides
        if emotion and emotion in director.emotion_to_visual:
            emotion_config = director.emotion_to_visual[emotion]
            params['emotion_colors'] = emotion_config.get('colors', [])
            params['emotion_motion'] = emotion_config.get('motion', 'gentle')
            params['emotion_lighting'] = emotion_config.get('lighting', 'natural')

        # Add philosophy context
        params['philosophy'] = {
            'central_theme': director.central_theme,
            'emotional_approach': director.emotional_approach,
            'visual_metaphor_style': director.visual_metaphor_style,
        }

        return params

    def generate_prompt_enhancement(self, base_prompt: str, style: str,
                                     emotional_dna: dict = None) -> str:
        """
        Enhance a generation prompt with director philosophy.

        This is the key innovation - prompts that capture WHY, not just WHAT.
        """
        director = self.get_director(style)
        if not director:
            return base_prompt

        # Build philosophy-informed prompt
        enhancements = []

        # Add visual philosophy
        enhancements.append(f"In the style of {director.name}")
        enhancements.append(f"Visual philosophy: {director.central_theme}")
        enhancements.append(f"Lighting: {director.lighting_approach}")
        enhancements.append(f"Camera: {director.camera_movement}")
        enhancements.append(f"Texture: {director.texture_preference}")

        # Add color philosophy
        color = director.color_philosophy
        enhancements.append(f"Color palette: {color.get('palette', 'cinematic')}")

        # Add emotion-specific guidance
        if emotional_dna:
            valence = emotional_dna.get('valence', 0)
            if valence < -0.3:
                emotion = 'sadness' if 'sadness' in director.emotion_to_visual else 'longing'
            elif valence > 0.3:
                emotion = 'joy' if 'joy' in director.emotion_to_visual else 'energy'
            else:
                emotion = 'nostalgia' if 'nostalgia' in director.emotion_to_visual else 'intimacy'

            if emotion in director.emotion_to_visual:
                e_config = director.emotion_to_visual[emotion]
                enhancements.append(f"Emotional approach: {e_config.get('approach', '')}")

        enhanced_prompt = f"{base_prompt}, {', '.join(enhancements)}"
        return enhanced_prompt

    def to_json(self, style: str) -> str:
        """Export director philosophy to JSON"""
        director = self.get_director(style)
        if not director:
            return "{}"

        return json.dumps({
            'name': director.name,
            'style_id': director.style_id,
            'central_theme': director.central_theme,
            'emotional_approach': director.emotional_approach,
            'visual_metaphor_style': director.visual_metaphor_style,
            'color_philosophy': director.color_philosophy,
            'lighting_approach': director.lighting_approach,
            'camera_movement': director.camera_movement,
            'editing_rhythm': director.editing_rhythm,
            'texture_preference': director.texture_preference,
            'default_params': director.default_params,
        }, indent=2)


# CLI for testing
if __name__ == "__main__":
    engine = DirectorPhilosophyEngine()

    print("Available Director Styles:")
    print("=" * 50)

    for style_id, director in engine.directors.items():
        print(f"\n{director.name} ({style_id})")
        print(f"  Theme: {director.central_theme}")
        print(f"  Approach: {director.emotional_approach}")

    # Test matching
    print("\n" + "=" * 50)
    print("Testing Audio-to-Director Matching:")

    test_dna = {
        'valence': -0.3,
        'arousal': 0.4,
        'dominance': 0.3,
        'warmth': 0.6,
        'genre_predictions': {'r_and_b': 0.6, 'hip_hop': 0.2},
    }

    best_match, confidence = engine.match_audio_to_director(test_dna)
    print(f"Best match: {best_match} (confidence: {confidence:.2f})")
