# New asset integration notes

The requested background asset is available at:
https://raw.githubusercontent.com/harshpromax137-web/Img/main/1788661333331.png

The saved background is `reference_background_source.png`, 1331 x 784 pixels, RGBA with fully opaque alpha. The API renderer uses this native canvas size.

The avatar PNG pattern resolves successfully for avatarId 102000015 at:
https://raw.githubusercontent.com/harshpromax137-web/Anime-PNG/main/102000015.png

The sample character PNG is 1536 x 2304 RGBA with a non-empty alpha channel. The API requests:
https://raw.githubusercontent.com/harshpromax137-web/Anime-PNG/main/{avatarId}.png
where `avatarId` is read from `profileInfo.avatarId`. The full-body character is cropped to its alpha bounds, fitted into the open center area between the eight outfit shapes, and alpha-composited behind the outfit item layers.

Offline preview: `new_background_character_preview.png` renders correctly at 1331 x 784 and places the character between the shapes. The source background itself contains placeholder/sample profile and stat text, so the production renderer must remove or cover those placeholders before writing live values; otherwise values can appear duplicated.

The cleaned offline preview was verified at 1331 x 784. The temporary API was restarted with the new renderer, and its public health endpoint returned HTTP 200 with status ok.
