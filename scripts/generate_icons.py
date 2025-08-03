#!/usr/bin/env python3
"""Generate PWA icons from base SVG."""

import subprocess
from pathlib import Path

# Define icon sizes
STANDARD_SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
MASKABLE_SIZES = [192, 512]
SHORTCUT_SIZE = 96

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
ICONS_DIR = PROJECT_ROOT / "app" / "static" / "assets" / "icons"
BASE_SVG = ICONS_DIR / "icon-base.svg"

def generate_standard_icons():
    """Generate standard PWA icons."""
    print("Generating standard icons...")
    for size in STANDARD_SIZES:
        output_file = ICONS_DIR / f"icon-{size}x{size}.png"
        print(f"  Creating {output_file.name}...")
        
        # Using ImageMagick convert or rsvg-convert if available
        # Fallback to creating placeholder if tools not available
        try:
            subprocess.run([
                "convert",
                "-background", "none",
                "-resize", f"{size}x{size}",
                str(BASE_SVG),
                str(output_file)
            ], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Create a simple placeholder PNG
            create_placeholder_png(output_file, size, "#7c3aed")

def generate_maskable_icons():
    """Generate maskable icons with safe zone padding."""
    print("Generating maskable icons...")
    for size in MASKABLE_SIZES:
        output_file = ICONS_DIR / f"icon-{size}x{size}-maskable.png"
        print(f"  Creating {output_file.name}...")
        
        # Maskable icons need 20% padding for safe zone
        padded_size = int(size * 0.8)
        try:
            subprocess.run([
                "convert",
                "-background", "#1a1a1a",
                "-resize", f"{padded_size}x{padded_size}",
                "-gravity", "center",
                "-extent", f"{size}x{size}",
                str(BASE_SVG),
                str(output_file)
            ], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Create a simple placeholder PNG
            create_placeholder_png(output_file, size, "#7c3aed", background="#1a1a1a")

def generate_shortcut_icon():
    """Generate shortcut icon."""
    print("Generating shortcut icon...")
    output_file = ICONS_DIR / f"shortcut-record.png"
    print(f"  Creating {output_file.name}...")
    
    try:
        subprocess.run([
            "convert",
            "-background", "none",
            "-resize", f"{SHORTCUT_SIZE}x{SHORTCUT_SIZE}",
            str(BASE_SVG),
            str(output_file)
        ], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Create a simple placeholder PNG
        create_placeholder_png(output_file, SHORTCUT_SIZE, "#7c3aed")

def create_placeholder_png(output_file, size, color, background="transparent"):
    """Create a simple colored square as placeholder."""
    # Using PIL if available, otherwise create using ImageMagick
    try:
        from PIL import Image, ImageDraw
        
        # Create image with background
        if background == "transparent":
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        else:
            # Convert hex to RGB
            bg_color = tuple(int(background[i:i+2], 16) for i in (1, 3, 5))
            img = Image.new('RGB', (size, size), bg_color)
        
        # Draw a circle in the center
        draw = ImageDraw.Draw(img)
        margin = size // 4
        circle_color = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        draw.ellipse([margin, margin, size-margin, size-margin], fill=circle_color)
        
        img.save(output_file, 'PNG')
    except ImportError:
        # Fallback to ImageMagick
        try:
            bg_opt = "none" if background == "transparent" else background
            subprocess.run([
                "convert",
                "-size", f"{size}x{size}",
                f"xc:{bg_opt}",
                "-fill", color,
                "-draw", f"circle {size//2},{size//2} {size//2},{size//4}",
                str(output_file)
            ], check=True, capture_output=True)
        except:
            # Last resort: create empty file
            output_file.touch()
            print(f"    Warning: Could not generate {output_file.name}")

def main():
    """Generate all PWA icons."""
    print(f"Generating PWA icons in {ICONS_DIR}")
    
    # Ensure icons directory exists
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Check if base SVG exists
    if not BASE_SVG.exists():
        print(f"Error: Base SVG not found at {BASE_SVG}")
        return 1
    
    # Generate icons
    generate_standard_icons()
    generate_maskable_icons()
    generate_shortcut_icon()
    
    print("\nIcon generation complete!")
    print(f"Icons saved to: {ICONS_DIR}")
    
    # List generated files
    print("\nGenerated files:")
    for icon_file in sorted(ICONS_DIR.glob("*.png")):
        print(f"  - {icon_file.name}")
    
    return 0

if __name__ == "__main__":
    exit(main())