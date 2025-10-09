#!/usr/bin/env python3
"""
Creative Automation Pipeline for Social Ad Campaigns
Uses Google Gemini 2.5 Flash Image model (recommended for image generation)
"""

import json
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    from google import genai
    from google.genai import types
    from PIL import Image
    from io import BytesIO
except ImportError:
    print("Error: Required packages not installed.")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)


class CreativeAutomationPipeline:
    """Main pipeline class for automating creative asset generation"""

    def __init__(self, api_key: Optional[str] = None, model: str = 'gemini-2.5-flash-image'):
        """
        Initialize the pipeline with Google Gemini API

        Args:
            api_key: Google Gemini API key (defaults to GEMINI_API_KEY env var)
            model: Model name (default: gemini-2.5-flash-image)
        """
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found. Set environment variable or pass as argument.")

        self.client = genai.Client(api_key=self.api_key)
        self.model = model
        self.output_dir = Path('generated_assets')
        self.output_dir.mkdir(exist_ok=True)

        # Aspect ratios for different platforms
        self.aspect_ratios = {
            '1x1': (1024, 1024),    # Instagram feed, Facebook post
            '9x16': (576, 1024),    # Instagram/Facebook Stories
            '16x9': (1024, 576)     # Display ads, YouTube
        }

        # Mapping for display purposes
        self.aspect_ratio_display = {
            '1x1': '1:1',
            '9x16': '9:16',
            '16x9': '16:9'
        }

        print(f"✓ Initialized with model: {self.model}")

    def load_campaign_brief(self, brief_path: str) -> Dict:
        """Load campaign brief from JSON or YAML file"""
        brief_file = Path(brief_path)

        if not brief_file.exists():
            raise FileNotFoundError(f"Campaign brief not found: {brief_path}")

        with open(brief_file, 'r') as f:
            if brief_file.suffix == '.json':
                return json.load(f)
            elif brief_file.suffix in ['.yaml', '.yml']:
                import yaml
                return yaml.safe_load(f)
            else:
                raise ValueError("Brief must be JSON or YAML format")

    def check_existing_assets(self, product: str, aspect_ratio: str) -> Optional[Path]:
        """Check if assets already exist for product and aspect ratio"""
        asset_path = self.output_dir / product / aspect_ratio
        if asset_path.exists() and list(asset_path.glob('*.png')):
            display_ratio = self.aspect_ratio_display.get(aspect_ratio, aspect_ratio)
            print(f"✓ Found existing assets for {product} ({display_ratio})")
            return asset_path
        return None

    def generate_image_prompt(self, brief: Dict, aspect_ratio: str, variant_num: int) -> str:
        """Generate detailed prompt for image generation"""
        product = brief.get('product', '').replace('_', ' ').title()
        audience = brief.get('target_audience', 'general audience')
        message = brief.get('campaign_message', '')
        region = brief.get('target_region', 'global')
        features = brief.get('key_features', [])

        display_ratio = self.aspect_ratio_display.get(aspect_ratio, aspect_ratio)

        # Create variation cues for different variants
        variant_styles = [
            "lifestyle shot with natural lighting",
            "close-up product detail with premium aesthetic",
            "environmental context showing product in use"
        ]
        style_cue = variant_styles[(variant_num - 1) % len(variant_styles)]

        # Build contextual prompt
        prompt = f"""Create a professional marketing photograph for {product}.

Style: {style_cue}
Target audience: {audience}
Message: {message}
Market: {region}

Visual requirements:
- Product prominently displayed and clearly visible
- Professional studio-quality lighting
- Clean, modern composition
- Brand-appropriate colors and aesthetic
- High-quality, photo-realistic rendering
- Suitable for {display_ratio} social media format

{f'Key features to highlight: {", ".join(features[:2])}' if features else ''}

Create an eye-catching, professional marketing image that would perform well in social media advertising."""

        return prompt

    def generate_creative_asset(
        self, 
        brief: Dict, 
        aspect_ratio: str,
        variant_num: int = 1
    ) -> Path:
        """Generate a single creative asset using Gemini API"""
        product = brief.get('product', 'unknown_product')

        # Create output directory structure
        product_dir = self.output_dir / product / aspect_ratio
        product_dir.mkdir(parents=True, exist_ok=True)

        # Generate prompt
        prompt = self.generate_image_prompt(brief, aspect_ratio, variant_num)

        display_ratio = self.aspect_ratio_display.get(aspect_ratio, aspect_ratio)
        print(f"\nGenerating {display_ratio} asset for {product} (variant {variant_num})...")

        try:
            # Call Gemini API for image generation
            # gemini-2.5-flash-image handles image generation natively
            response = self.client.models.generate_content(
                model=self.model,
                contents=[prompt]
            )

            # Extract and save image
            image_found = False
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image = Image.open(BytesIO(part.inline_data.data))

                    # Resize to target aspect ratio
                    target_size = self.aspect_ratios.get(aspect_ratio, (1024, 1024))
                    image = image.resize(target_size, Image.Resampling.LANCZOS)

                    # Save image
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{product}_{aspect_ratio}_v{variant_num}_{timestamp}.png"
                    output_path = product_dir / filename

                    image.save(output_path)
                    print(f"✓ Saved: {output_path}")
                    image_found = True
                    return output_path
                elif part.text is not None:
                    print(f"  Response text: {part.text[:150]}...")

            if not image_found:
                raise Exception(f"No image data in response from {self.model}")

        except Exception as e:
            print(f"✗ Error generating asset: {str(e)}")
            raise

    def generate_campaign_message(self, brief: Dict, locale: str = 'en') -> str:
        """Generate localized campaign message"""
        base_message = brief.get('campaign_message', '')

        if locale == 'en':
            return base_message

        print(f"Note: Localization for '{locale}' not yet implemented. Using English.")
        return base_message

    def run_pipeline(
        self, 
        brief_path: str, 
        num_variants: int = 3,
        skip_existing: bool = True
    ) -> Dict[str, List[Path]]:
        """Run complete pipeline for campaign brief"""
        print("="*60)
        print("Creative Automation Pipeline - Starting")
        print("="*60)

        # Load campaign brief
        brief = self.load_campaign_brief(brief_path)
        product = brief.get('product', 'unknown_product')

        print(f"\nProduct: {product}")
        print(f"Target Region: {brief.get('target_region', 'N/A')}")
        print(f"Target Audience: {brief.get('target_audience', 'N/A')}")
        print(f"Campaign Message: {brief.get('campaign_message', 'N/A')}")

        results = {}

        # Generate assets for each aspect ratio
        for aspect_ratio in self.aspect_ratios.keys():
            display_ratio = self.aspect_ratio_display[aspect_ratio]
            print(f"\n--- Processing {display_ratio} aspect ratio ---")

            # Check for existing assets
            if skip_existing and self.check_existing_assets(product, aspect_ratio):
                existing_path = self.output_dir / product / aspect_ratio
                results[display_ratio] = list(existing_path.glob('*.png'))
                continue

            # Generate variants
            variant_paths = []
            for i in range(1, num_variants + 1):
                try:
                    path = self.generate_creative_asset(brief, aspect_ratio, i)
                    variant_paths.append(path)
                except Exception as e:
                    print(f"Failed to generate variant {i}: {str(e)}")

            results[display_ratio] = variant_paths

        # Generate campaign message
        print("\n--- Campaign Message ---")
        message = self.generate_campaign_message(brief, locale='en')
        print(f"English: {message}")

        # Print summary
        print("\n" + "="*60)
        print("Pipeline Complete - Summary")
        print("="*60)
        total_assets = sum(len(paths) for paths in results.values())
        print(f"Total assets generated: {total_assets}")

        for ratio, paths in results.items():
            print(f"  {ratio}: {len(paths)} variants")

        print(f"\nOutput directory: {self.output_dir / product}")
        print("="*60)

        return results


def main():
    """Main entry point for CLI"""
    parser = argparse.ArgumentParser(
        description='Creative Automation Pipeline for Social Ad Campaigns'
    )
    parser.add_argument(
        'brief',
        help='Path to campaign brief (JSON or YAML)'
    )
    parser.add_argument(
        '--variants',
        type=int,
        default=3,
        help='Number of variants per aspect ratio (default: 3)'
    )
    parser.add_argument(
        '--no-skip',
        action='store_true',
        help='Regenerate even if assets exist'
    )
    parser.add_argument(
        '--api-key',
        help='Google Gemini API key (optional, uses GEMINI_API_KEY env var)'
    )
    parser.add_argument(
        '--model',
        default='gemini-2.5-flash-image',
        choices=['gemini-2.5-flash-image', 'gemini-2.0-flash-exp'],
        help='Model to use for image generation (default: gemini-2.5-flash-image)'
    )

    args = parser.parse_args()

    try:
        pipeline = CreativeAutomationPipeline(api_key=args.api_key, model=args.model)
        pipeline.run_pipeline(
            args.brief,
            num_variants=args.variants,
            skip_existing=not args.no_skip
        )
    except Exception as e:
        print(f"\nError: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
