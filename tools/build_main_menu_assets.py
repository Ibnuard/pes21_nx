"""Prepare compact PNG payloads for the custom full-page main menu."""

from pathlib import Path
from shutil import copyfile

from PIL import Image, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "art" / "main_menu"
DATA = ROOT / "data"


def save_payload(image: Image.Image, art_name: str, data_name: str) -> None:
    art_path = ART / art_name
    image.save(art_path, "PNG", optimize=True)
    copyfile(art_path, DATA / data_name)


def normalized_portrait(source: Path) -> Image.Image:
    image = Image.open(source).convert("RGBA")
    # Several supplied cutouts contain almost-invisible alpha noise hundreds of
    # pixels above the real subject.  A raw getbbox() treats that noise as body
    # content and makes the visible player much smaller than the clean Ronaldo
    # anchor.  Crop only from confidently visible alpha.
    alpha_box = image.getchannel("A").point(
        lambda alpha: 255 if alpha >= 32 else 0
    ).getbbox()
    if not alpha_box:
        raise ValueError(f"portrait has no visible pixels: {source}")
    image = image.crop(alpha_box)
    image = ImageEnhance.Color(image).enhance(1.04)
    image = ImageEnhance.Contrast(image).enhance(1.05)
    image = ImageEnhance.Sharpness(image).enhance(1.12)
    canvas_size = (768, 1024)
    scale = min(744 / image.width, 1000 / image.height)
    size = (max(1, round(image.width * scale)),
            max(1, round(image.height * scale)))
    image = image.resize(size, Image.Resampling.LANCZOS)
    image = image.filter(ImageFilter.UnsharpMask(radius=0.7, percent=55,
                                                  threshold=3))
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    canvas.alpha_composite(image, ((canvas_size[0] - size[0]) // 2,
                                   canvas_size[1] - size[1] + 8))
    return canvas


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    copyfile(ROOT / "art" / "SwitchButton" / "A_Button.png",
             DATA / "main_menu_button_a.bin")

    background = Image.open(ART / "background-v1.png").convert("RGB")
    background = background.resize((1280, 720), Image.Resampling.LANCZOS)
    save_payload(background, "background-runtime.png",
                 "main_menu_background.bin")

    icon_alpha = Image.open(ART / "icons-mask-v1.png").convert("L")
    icon_alpha = icon_alpha.resize((512, 512), Image.Resampling.LANCZOS)
    # The overlay treats this atlas as a tintable luminance mask.  Keep RGB and
    # alpha identical so transparent atlas space never becomes a solid square.
    icons = Image.merge("RGBA", (icon_alpha, icon_alpha,
                                  icon_alpha, icon_alpha))
    save_payload(icons, "icons-runtime.png", "main_menu_icons.bin")

    brand = Image.open(ART / "brand-logo-source.png").convert("RGBA")
    brand_box = brand.getchannel("A").point(
        lambda alpha: 255 if alpha >= 8 else 0
    ).getbbox()
    if not brand_box:
        raise ValueError("main-menu brand logo has no visible pixels")
    brand = brand.crop(brand_box)
    save_payload(brand, "brand-logo-runtime.png", "main_menu_brand.bin")

    portraits = (
        ("portrait-exhibition-source.png", "portrait-exhibition.png",
         "main_menu_portrait_exhibition.bin"),
        ("portrait-2player-source.png", "portrait-2player.png",
         "main_menu_portrait_2player.bin"),
        ("portrait-settings-source.png", "portrait-settings.png",
         "main_menu_portrait_settings.bin"),
        ("portrait-credits-source.png", "portrait-credits.png",
         "main_menu_portrait_credits.bin"),
    )
    for source, art_name, data_name in portraits:
        save_payload(normalized_portrait(ART / source), art_name, data_name)


if __name__ == "__main__":
    main()
