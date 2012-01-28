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

    x = y = 0


class Game(object):

    PADDING = 2
    STARTED = object()
    LOADING = object()
    zoom = 1.0

    def __init__(self):
        self.x, self.y = 5, 5
        self.camera = Camera()
        self.tiles = {}
        self.state = self.LOADING

    @property
    def drawable_tiles(self):
        tiles = []
        for x in range(self.x - self.PADDING, self.x + self.PADDING):
            for y in range(self.y - self.PADDING, self.y + self.PADDING):
                tiles.append(self.tiles[x, y])
        return tiles

    @property
    def missing_tiles(self):
        tiles = []
        for x in range(16):
            for y in range(10):
                if (x, y) not in self.tiles:
                    tiles.append((x, y))
        return tiles

    def move_left(self):
        self.camera.x -= 200

    def move_right(self):
        self.camera.x += 200

    def move_up(self):
        self.camera.y += 200

    def move_down(self):
        self.camera.y -= 200

    def draw(self):
        if self.state == self.STARTED:
            gl.glTranslatef(window.width / 2, window.height // 2, 0)
            gl.glScalef(self.zoom, self.zoom, 1.0)
            gl.glTranslatef(-window.width / 2, -window.height // 2, 0)
            gl.glTranslatef(self.camera.x * -1, self.camera.y * -1, 0)
            for tile in self.drawable_tiles:
                tile.draw()
        else:
            missing_tiles = self.missing_tiles
            if missing_tiles:
                self.load_tile(*self.missing_tiles[0])
            else:
                self.state = self.STARTED

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
            self.zoom *= 1.1
        if symbol == key.MINUS:
            self.zoom /= 1.1
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

