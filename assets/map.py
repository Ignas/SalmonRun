#!/usr/bin/python
import sys
from PIL import Image

tile_size = (1024, 1024)


def main():
    img = Image.open(sys.argv[1])
    tile_w, tile_h = tile_size
    img_w, img_h = img.size
    for row, y in enumerate(range(0, img_h, tile_h)):
        for col, x in enumerate(range(0, img_w, tile_w)):
            filename = 'tile-%03d-%03d.png' % (row, col)
            w = min(tile_w, img_w - x)
            h = min(tile_h, img_h - y)
            img.crop((x, y, x+w, y+h)).save(filename)


if __name__ == '__main__':
    main()
