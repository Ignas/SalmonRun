#!/usr/bin/env python
import math
import logging
import time
from contextlib import contextmanager

import pyglet
from pyglet.window import key
from pyglet import gl


DEBUG_VERSION = False
TILE_SIZE = 1024

log = logging.getLogger('salmon')

if DEBUG_VERSION:
    log.setLevel(logging.DEBUG)
    log.addHandler(logging.StreamHandler())


pyglet.resource.path = ['assets']
pyglet.resource.reindex()


window = None


def load_image(filename, **kw):
    img = pyglet.resource.image(filename)
    for k, v in kw.items():
        setattr(img, k, v)
    return img

def get_mem_usage():
    return int(open('/proc/self/stat').read().split()[22])

@contextmanager
def gl_matrix():
    gl.glPushMatrix()
    try:
        yield
    finally:
        gl.glPopMatrix()


@contextmanager
def gl_state(bits=gl.GL_ALL_ATTRIB_BITS):
    gl.glPushAttrib(bits)
    try:
        yield
    finally:
        gl.glPopAttrib()



class Camera(object):

    def __init__(self, game):
        self.game = game
        self.x = self.game.map_x
        self.y = self.game.map_y
        self.zoom = self.game.zoom
        self.target_x = self.x
        self.target_y = self.y
        self.target_zoom = self.zoom
        self.focus = None
        self.focus_timer = 0

    @property
    def center_x(self):
        return int(self.target_x + window.width // 2)

    @property
    def center_y(self):
        return int(self.target_y + window.height // 2)

    @center_x.setter
    def center_x(self, x):
        self.target_x = int(x - window.width // 2)

    @center_y.setter
    def center_y(self, y):
        self.target_y = int(y - window.height // 2)

    @property
    def bottom_third_y(self):
        return int(self.target_y + window.height // 3)

    @bottom_third_y.setter
    def bottom_third_y(self, y):
        self.target_y = int(y - window.height // 3)

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @x.setter
    def x(self, x):
        self._x = max(0, x)

    @y.setter
    def y(self, y):
        self._y = max(0, y)

    def focus_on(self, obj):
        self.focus = obj
        self.focus_timer = 0

    def remove_focus(self, obj):
        if self.focus is obj:
            self.focus_timer = 1 # seconds

    def update(self, dt):
        self.target_x = self.game.map_x
        self.target_y = self.game.map_y
        self.target_zoom = self.game.zoom
        self.x = int(self.x - (self.x - self.target_x) * 0.1)
        self.y = int(self.y - (self.y - self.target_y) * 0.1)
        self.zoom = self.zoom - (self.zoom - self.target_zoom) * 0.1


class Level(object):

    def __init__(self):
        self.path = [(5000, 5000),
                     (300, 500)]

class Game(object):

    MAP_W, MAP_H = 16, 10

    last_load_time = None

    TILE_PADDING = 2
    STARTED = object()
    LOADING = object()
    zoom = 0.4
    update_freq = 1 / 60.

    def __init__(self):
        self.map_x, self.map_y = 1024 * 8, 1024 * 4
        self.camera = Camera(self)
        pyglet.clock.schedule_interval(self.camera.update, self.update_freq)

        self.tiles = {}
        self.load_time = {}
        self.state = self.LOADING
        self.missing_tiles = [(x, y) for x in range(self.MAP_W)
                                     for y in range(self.MAP_H)]
        self.missing_tiles.sort(key=lambda (x, y): math.hypot(x - self.tile_x,
                                                              y - self.tile_y))

    @property
    def tile_x(self):
        return self.camera.x / 1024

    @property
    def tile_y(self):
        return self.camera.y / 1024

    @property
    def drawable_tiles(self):
        tiles = []
        for x in range(self.tile_x - self.TILE_PADDING, self.tile_x + self.TILE_PADDING + 1):
            for y in range(self.tile_y - self.TILE_PADDING, self.tile_y + self.TILE_PADDING + 1):
                if (x, y) in self.tiles:
                    tiles.append(self.tiles[x, y])
        return tiles

    def move_left(self):
        self.map_x = max(0, self.map_x - 1024)

    def move_right(self):
        self.map_x += 1024

    def move_up(self):
        self.map_y = max(0, self.map_y - 1024)

    def move_down(self):
        self.map_y += 1024

    def draw(self):
        if self.missing_tiles:
            if (self.last_load_time is None or
                time.time() - self.last_load_time > 0.1):
                self.load_tile(*self.missing_tiles.pop(0))
                self.last_load_time = time.time()
        gl.glTranslatef(window.width / 2, window.height // 2, 0)
        gl.glScalef(self.camera.zoom, self.camera.zoom, 1.0)
        gl.glTranslatef(-self.camera.x, self.camera.y, 0)
        for tile in self.drawable_tiles:
            if tile.opacity < 255:
                tile.opacity = min(255, int((time.time() - tile.loaded) * 255))
            tile.draw()

    def load_tile(self, x, y):
        filename = 'tile-%03d-%03d.png' % (y, x)
        mu = get_mem_usage()
        image = load_image(filename)
        image.anchor_x = image.anchor_y = TILE_SIZE / 2
        dmem = get_mem_usage() - mu
        sprite = self.tiles[x, y] = pyglet.sprite.Sprite(image)
        sprite.loaded = time.time()
        sprite.opacity = 0
        sprite.x = TILE_SIZE * x
        sprite.y = -TILE_SIZE * y
        # print "Loaded:", filename, dmem, get_mem_usage() - mu - dmem, get_mem_usage() / 1024 / 1024


class Main(pyglet.window.Window):

    fps_display = None

    def __init__(self):
        super(Main, self).__init__(width=1024, height=600,
                                   resizable=True,
                                   caption='Salmon Run')
        self.set_minimum_size(320, 200) # does not work on linux with compiz
        # self.set_fullscreen()
        self.set_mouse_visible(True)
        # self.set_icon(pyglet.image.load(
        #         os.path.join(pyglet.resource.location('Dodo.png').path, 'Dodo.png')))
        self.background_batch = pyglet.graphics.Batch()
        self.game = Game()

        self.fps_display = pyglet.clock.ClockDisplay()
        self.fps_display.label.y = self.height - 50
        self.fps_display.label.x = self.width - 170

    def on_draw(self):
        self.clear()
        with gl_matrix():
            self.game.draw()
        if self.fps_display:
            self.fps_display.draw()

    def on_text_motion(self, motion):
        if motion == key.LEFT:
            self.game.move_left()
        elif motion == key.RIGHT:
            self.game.move_right()
        elif motion == key.UP:
            self.game.move_up()
        elif motion == key.DOWN:
            self.game.move_down()

    def on_key_press(self, symbol, modifiers):
        if symbol == key.ESCAPE:
            self.dispatch_event('on_close')

        if symbol == key.F:
            self.set_fullscreen(not self.fullscreen)
        if symbol in [key.PLUS, key.EQUAL]:
            self.game.zoom *= 1.5
        if symbol == key.MINUS:
            self.game.zoom /= 1.5

        # DEBUG/CHEAT CODES
        if not DEBUG_VERSION:
            return

    def on_resize(self, width, height):
        if self.fps_display:
            self.fps_display.label.y = self.height - 50
            self.fps_display.label.x = self.width - 170
        super(Main, self).on_resize(width, height)

    def run(self):
        pyglet.app.run()


def main():
    global window
    window = Main()
    window.run()


if __name__ == '__main__':
    main()

