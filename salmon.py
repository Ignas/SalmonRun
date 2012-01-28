#!/usr/bin/env python
import time
import itertools
import logging
from threading import Thread, Lock
from contextlib import contextmanager

import pyglet
from pyglet.window import key
from pyglet import gl


DEBUG_VERSION = False
TILE_SIZE = 1024

log = logging.getLogger('dodo')

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
        self.target_x = self.x
        self.target_y = self.y
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
        self.x = int(self.x - (self.x - self.target_x) * 0.1)
        self.y = int(self.y - (self.y - self.target_y) * 0.1)
        if self.focus:
            self.center_x, self.center_y = self.focus.x, self.focus.y
            if self.focus_timer > 0:
                self.focus_timer -= dt
                if self.focus_timer <= 0:
                    self.focus_on(None)
        else:
            self.center_x, self.bottom_third_y = self.game.map_x, self.game.map_y


class Game(object):

    TILE_PADDING = 1
    STARTED = object()
    LOADING = object()
    zoom = 1.0
    update_freq = 1 / 60.

    def __init__(self):
        self.map_x, self.map_y = 300, 300
        self.camera = Camera(self)
        pyglet.clock.schedule_interval(self.camera.update, self.update_freq)

        self.tiles = {}
        self.state = self.LOADING
        self.missing_tiles = []
        for x in range(16 + 10):
            for y in range(10):
                if x >= y and (x - y) < 16:
                    self.missing_tiles.append((x - y, y))

    @property
    def tile_x(self):
        return self.map_x / 1024

    @property
    def tile_y(self):
        return self.map_y / 1024

    @property
    def drawable_tiles(self):
        tiles = []
        for x in range(self.tile_x - self.TILE_PADDING, self.tile_x + self.TILE_PADDING + 1):
            for y in range(self.tile_y - self.TILE_PADDING, self.tile_y + self.TILE_PADDING + 1):
                if (x, y) in self.tiles:
                    tiles.append(self.tiles[x, y])
        return tiles

    def move_left(self):
        self.map_x -= 200

    def move_right(self):
        self.map_x += 200

    def move_up(self):
        self.map_y -= 200

    def move_down(self):
        self.map_y += 200

    def draw(self):
        if self.missing_tiles:
            self.load_tile(*self.missing_tiles.pop(0))
        else:
            self.state = self.STARTED
        gl.glTranslatef(window.width / 2, window.height // 2, 0)
        gl.glScalef(self.zoom, self.zoom, 1.0)
        gl.glTranslatef(-window.width / 2, -window.height // 2, 0)
        gl.glTranslatef(self.camera.x * -1, self.camera.y * -1, 0)
        for tile in self.drawable_tiles:
            tile.draw()

    def load_tile(self, x, y):
        filename = 'tile-%03d-%03d.png' % (y, x)
        mu = get_mem_usage()
        image = load_image(filename)
        dmem = get_mem_usage() - mu
        sprite = self.tiles[x, y] = pyglet.sprite.Sprite(image)
        sprite.x = TILE_SIZE * x
        sprite.y = -TILE_SIZE * y
        print "Loaded:", filename, dmem, get_mem_usage() - mu - dmem, get_mem_usage() / 1024 / 1024


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
            self.game.zoom *= 1.1
        if symbol == key.MINUS:
            self.game.zoom /= 1.1
        if symbol == key.N:
            self.new_game()

        # DEBUG/CHEAT CODES
        if not DEBUG_VERSION:
            return

        if symbol == key.ASCIITILDE:
            g = self.game
            g.sea.level = max(g.sea.level + 10,
                              g.current_level.height - self.height // 2)
        if symbol == key.SLASH:
            # Note: leaves update() methods running, which maybe ain't bad
            # -- eradicating a dodo mid-flight won't leave the camera focus
            # stuck on it then
            for dodo in self.game.dodos[::2]:
                dodo.sprite.visible = False
            del self.game.dodos[::2]
        if symbol == key.L:
            if (self.game.current_level.next is not None and
                self.game.current_level.next.next is not None):
                self.game.next_level()
        if symbol == key.G:
            self.game.game_over()

    def on_key_release(self, symbol, modifiers):
        if symbol == key.SPACE:
            self.game.dodopult.fire()

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

