from pathlib import Path
from urllib.request import urlopen
from PIL import Image

root = Path(__file__).parent
avatar_url = "https://raw.githubusercontent.com/harshpromax137-web/Anime-PNG/main/102000015.png"
avatar_path = root / "sample_avatar_102000015.png"
with urlopen(avatar_url, timeout=20) as response:
    avatar_path.write_bytes(response.read())

for path in (root / "reference_background_source.png", avatar_path):
    image = Image.open(path)
    print(path.name, image.size, image.mode)
    if "A" in image.getbands():
        alpha = image.getchannel("A")
        print("alpha_extrema", alpha.getextrema())
