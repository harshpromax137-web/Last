from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).parent
source_path = root / "reference_background_source.png"
output_path = root / "clean_reference_background.png"
image = Image.open(source_path).convert("RGBA")
draw = ImageDraw.Draw(image, "RGBA")

# Clean the light profile card interior so live avatar/name/UID/clan/likes can be drawn once.
profile_fill = (238, 238, 238, 255)
draw.rectangle((934, 100, 1268, 202), fill=profile_fill)
# Remove the sample level and bottom UID text but leave the gift icon and card borders intact.
draw.rectangle((894, 195, 984, 227), fill=(151, 89, 22, 255))
draw.rectangle((1090, 196, 1202, 227), fill=(35, 18, 31, 255))

# Remove only the sample numeric values in the statistics value column; preserve labels and row rules.
for top, bottom in ((282, 315), (319, 354), (358, 393), (397, 432), (436, 472)):
    draw.rectangle((1145, top, 1268, bottom), fill=(12, 12, 12, 225))

image.save(output_path, format="PNG")
print(output_path)
