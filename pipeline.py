#!/usr/bin/env python3
"""
Creative Automation Pipeline for Social Ad Campaigns
Uses Google Gemini API for image generation
"""

import json
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import sys


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

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the pipeline with Google Gemini API

        Args:
            api_key: Google Gemini API key (defaults to GEMINI_API_KEY env var)
        """
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found. Set environment variable or pass as argument.")

        self.client = genai.Client(api_key=self.api_key)
        self.output_dir = Path('generated_assets')
        self.output_dir.mkdir(exist_ok=True)

        # Aspect ratios for different platforms
        self.aspect_ratios = {
            '1:1': (1024, 1024),    # Instagram feed, Facebook post
            '9:16': (576, 1024),    # Instagram/Facebook Stories
            '16:9': (1024, 576)     # Display ads, YouTube
        }

    def load_campaign_brief(self, brief_path: str) -> Dict:
        """
        Load campaign brief from JSON or YAML file

        Args:
            brief_path: Path to campaign brief file

        Returns:
            Parsed campaign brief dictionary
        """
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
        """
        Check if assets already exist for product and aspect ratio

        Args:
            product: Product name/ID
            aspect_ratio: Aspect ratio (e.g., '1:1')

        Returns:
            Path to existing asset or None
        """
        asset_path = self.output_dir / product / aspect_ratio
        if asset_path.exists() and list(asset_path.glob('*.png')):
            print(f"✓ Found existing assets for {product} ({aspect_ratio})")
            return asset_path
        return None

    def generate_image_prompt(self, brief: Dict, aspect_ratio: str) -> str:
        """
        Generate detailed prompt for image generation

        Args:
            brief: Campaign brief dictionary
            aspect_ratio: Target aspect ratio

        Returns:
            Formatted prompt string
        """
        product = brief.get('product', '')
        audience = brief.get('target_audience', 'general audience')
        message = brief.get('campaign_message', '')
        region = brief.get('target_region', 'global')

        # Build contextual prompt
        prompt = f"""Create a high-quality professional marketing image for {product}.
Target audience: {audience}
Campaign message: {message}
Market: {region}
Style: Modern, clean, professional social media advertisement
Include: Product prominently displayed, attractive composition, brand-appropriate colors
Format: {aspect_ratio} aspect ratio suitable for social media"""

        return prompt

    def generate_creative_asset(
        self, 
        brief: Dict, 
        aspect_ratio: str,
        variant_num: int = 1
    ) -> Path:
        """
        Generate a single creative asset using Gemini API

        Args:
            brief: Campaign brief dictionary
            aspect_ratio: Target aspect ratio
            variant_num: Variant number for naming

        Returns:
            Path to generated image
        """
        product = brief.get('product', 'unknown_product')

        # Create output directory structure
        product_dir = self.output_dir / product / aspect_ratio
        product_dir.mkdir(parents=True, exist_ok=True)

        # Generate prompt
        prompt = self.generate_image_prompt(brief, aspect_ratio)

        print(f"\nGenerating {aspect_ratio} asset for {product} (variant {variant_num})...")

        try:
            # Call Gemini API for image generation
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=[prompt]
            )

            # Extract and save image
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image = Image.open(BytesIO(part.inline_data.data))

                    # Resize to target aspect ratio
                    target_size = self.aspect_ratios.get(aspect_ratio, (1024, 1024))
                    image = image.resize(target_size, Image.Resampling.LANCZOS)

                    # Save image
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{product}_{aspect_ratio.replace(':', 'x')}_v{variant_num}_{timestamp}.png"
                    output_path = product_dir / filename

                    image.save(output_path)
                    print(f"✓ Saved: {output_path}")
                    return output_path

            raise Exception("No image data in response")

        except Exception as e:
            print(f"✗ Error generating asset: {str(e)}")
            raise

    def generate_campaign_message(self, brief: Dict, locale: str = 'en') -> str:
        """
        Generate localized campaign message

        Args:
            brief: Campaign brief dictionary
            locale: Target locale (default: 'en' for English)

        Returns:
            Localized campaign message
        """
        base_message = brief.get('campaign_message', '')

        # For POC, return English message
        # In production, integrate translation API
        if locale == 'en':
            return base_message

        # Placeholder for localization
        print(f"Note: Localization for '{locale}' not yet implemented. Using English.")
        return base_message

    def run_pipeline(
        self, 
        brief_path: str, 
        num_variants: int = 3,
        skip_existing: bool = True
    ) -> Dict[str, List[Path]]:
        """
        Run complete pipeline for campaign brief

        Args:
            brief_path: Path to campaign brief file
            num_variants: Number of variants to generate per aspect ratio
            skip_existing: Skip generation if assets exist

        Returns:
            Dictionary mapping aspect ratios to generated asset paths
        """
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
            print(f"\n--- Processing {aspect_ratio} aspect ratio ---")

            # Check for existing assets
            if skip_existing and self.check_existing_assets(product, aspect_ratio):
                existing_path = self.output_dir / product / aspect_ratio
                results[aspect_ratio] = list(existing_path.glob('*.png'))
                continue

            # Generate variants
            variant_paths = []
            for i in range(1, num_variants + 1):
                try:
                    path = self.generate_creative_asset(brief, aspect_ratio, i)
                    variant_paths.append(path)
                except Exception as e:
                    print(f"Failed to generate variant {i}: {str(e)}")

            results[aspect_ratio] = variant_paths

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

    args = parser.parse_args()

    try:
        pipeline = CreativeAutomationPipeline(api_key=args.api_key)
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
