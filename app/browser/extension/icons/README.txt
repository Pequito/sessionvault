Convert icon.svg to the three required PNG sizes before loading the extension:

  Using Inkscape (CLI):
    inkscape icon.svg -w 16  -h 16  -o icon16.png
    inkscape icon.svg -w 48  -h 48  -o icon48.png
    inkscape icon.svg -w 128 -h 128 -o icon128.png

  Using ImageMagick:
    convert -background none icon.svg -resize 16x16   icon16.png
    convert -background none icon.svg -resize 48x48   icon48.png
    convert -background none icon.svg -resize 128x128 icon128.png

The extension works without icons (the browser will use a grey puzzle-piece
placeholder) until the PNGs are generated.
