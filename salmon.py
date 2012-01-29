#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from lxml import etree
import random
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
font = dict(font_name='Andale Mono',
            font_size=20)


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


class River(object):

    parent_node = 0

    def __init__(self, title, nodes, parent=None):
        self.title = title
        self.tributaries = {}
        self.parent = parent
        self.nodes = nodes

        rx, ry = self.nodes[0]
        if self.parent is not None:
            closest = min([(math.hypot(rx - x, ry - y), (x, y))
                           for x, y in self.parent.nodes])
            self.parent_node = self.parent.nodes.index(closest[1])
            self.parent.tributaries[self.parent_node] = self
        # XXX code that finds out which options should be shown
        self.choices = ['UP', 'DOWN']

    def path(self, start_from=0):
        nodes = self.nodes
        if start_from:
            nodes = self.nodes[:start_from]
        for node in reversed(nodes):
            yield node
        if self.parent:
            for node in self.parent.path(self.parent_node):
                yield node


class Game(object):

    MAP_W, MAP_H = 16+1, 10+1

    last_load_time = None

    TILE_PADDING = 2
    LOADING = object()
    LOADED = object()
    BACKTRACKING = object()
    STARTED = object()
    zoom = 0.5
    update_freq = 1 / 60.
    skip_loading = True

    def __init__(self):
        self.map_x, self.map_y = 1024 * 8, 1024 * 4
        self.camera = Camera(self)
        pyglet.clock.schedule_interval(self.camera.update, self.update_freq)
        pyglet.clock.schedule_interval(self.update, self.update_freq)

        self.tiles = {}
        self.missing_tile = self.load_tile_sprite('no-tile.png')
        self.load_time = {}
        self.state = self.LOADING
        self.missing_tiles = [(x, y) for x in range(self.MAP_W)
                                     for y in range(self.MAP_H)]
        self.total_tiles = len(self.missing_tiles)


        baseinas = pyglet.resource.file('nemunas_clean.svg')
        tree = etree.parse(baseinas)

        def d_to_coords(d, px=0, py=0):
            coords = []
            d = d.split(' ')
            [current_x, current_y] = map(float, d[1].split(","))
            current_x += px
            current_y += py
            coords.append((current_x, current_y))
            coordinates = d[3:]
            for n, coord in enumerate(coordinates):
                if n % 3 == 2:
                    dx, dy = map(float, coord.split(","))
                    current_x = dx + px
                    current_y = dy + py
                    coords.append((current_x, current_y))
            return coords

        def multiply(coords, k, l=None):
            if l is None:
                l = k
            return [(x * k, y * l)
                    for (x, y) in coords]

        def offset(coords, offset_x=0, offset_y=0):
            return [(x + offset_x, y + offset_y)
                    for (x, y) in coords]

        def translate_offset(transform):
            if transform.startswith('translate('):
                dx, dy = map(float,
                             transform.split('(')[1].split(')')[0].split(','))
                return (dx, y)
            return (0, 0)

        n1 = tree.xpath("//*[@id='Nemunas1']/@d")[0]
        t1 = tree.xpath("//*[@id='Nemunas1']/../@transform")[0]
        n2 = tree.xpath("//*[@id='Nemunas2']/@d")[0]
        t2 = tree.xpath("//*[@id='Nemunas2']/../@transform")[0]
        nemunas = d_to_coords(n1, *translate_offset(t1))
        nemunas += d_to_coords(n2, *translate_offset(t2))
        nemunas = multiply(nemunas, 6.0, 6.0)

        # When exporting png coordinates got shifted a little bit, so
        # we compensate for it
        nemunas = offset(nemunas, -512 + 95, +512 + 1024 + 42)
        self.nemunas = River("Nemunas", nemunas)

        def load_river(title, river_id, parent):
            # Refactor us please, we feel duplicated
            river = tree.xpath("//*[@id='%s']/@d" % river_id)[0]
            river = d_to_coords(river)
            river = multiply(river, 6.0, 6.0)
            river = offset(river, -512 + 95, -304)
            return River(title, river, parent)

        sesupe = load_river(u"Šešupė", "sesupe", self.nemunas)
        jotija_onija = load_river(u"Jotija-Onija", "jotija-onija", sesupe)
        jotija = load_river(u"Jotija", "jotija", jotija_onija)
        siesartis = load_river(u"Siesartis", "siesartis", sesupe)
        nova = load_river(u"Nova", "nova", sesupe)
        penta = load_river(u"Penta", "penta", nova)
        visakis = load_river(u"Višakis", "visakis", sesupe)
        jure = load_river(u"Jūrė", "jure", visakis)
        pilve = load_river(u"Pilvė", "pilve", sesupe)
        kirsna = load_river(u"Kirsna", "kirsna", sesupe)
        dovine = load_river(u"Dovinė", "dovine", sesupe)

        self.levels = [sesupe,
                       jotija,
                       jotija_onija,
                       siesartis,
                       nova,
                       penta,
                       jure,
                       pilve,
                       kirsna,
                       dovine]
        # self.level = random.choice(self.levels)
        # self.path = self.level.path()
        # dot_image = load_image("dot.png")
        # dot_image.anchor_x = dot_image.anchor_y = 8
        self.dots = []
        # for x, y in self.level.path():
        #     sprite = pyglet.sprite.Sprite(dot_image)
        #     self.dots.append(sprite)
        #     sprite.x = x
        #     sprite.y = -y

    flashes = []
    def flash(self, flash, t):
        self.flashes.append((t, flash))

    def draw_flashes(self):
        for t, flash in self.flashes:
            flash.draw()

    def update_flashes(self, dt):
        self.flashes = [(t - dt, flash)
                        for (t, flash) in self.flashes
                        if t - dt > 0]

    def flash_text(self, text, x, y, t):
        label = pyglet.text.Label(text, x=x, y=y, **font)
        label.height = 20
        label.width = len(text) * 20
        self.flash(label, t)

    last_move_time = None
    def update(self, dt):
        self.update_flashes(dt)
        if (self.state == self.LOADING or
            self.skip_loading):
            if self.missing_tiles:
                if (self.last_load_time is None or
                    time.time() - self.last_load_time > 0.1):
                    self.missing_tiles.sort(
                        key=lambda (x, y): math.hypot(x - self.tile_x,
                                                      y - self.tile_y))
                    self.load_tile(*self.missing_tiles.pop(0))
                    self.last_load_time = time.time()

            if (self.state == self.LOADING and
                (self.skip_loading or (not self.missing_tiles))):
                self.state = self.LOADED

        if self.state is self.LOADED:
            self.level = random.choice(self.levels)
            self.path = self.level.path()
            self.zoom = 3
            self.map_x, self.map_y = self.path.next()
            self.state = self.BACKTRACKING
            self.flash_text(u"Lašiša gimė upėje kuri vadinasi %s" % self.level.title, 50, 50, t=5)
            self.last_move_time = time.time() + 5

        if self.state is self.BACKTRACKING:
            try:
                if (time.time() - self.last_move_time > 0.2):
                    node = self.path.next()
                    self.map_x, self.map_y = node
                    self.last_move_time = time.time()
            except StopIteration:
                self.state = self.STARTED
        elif self.state is self.STARTED:
            # node = self.path.next()
            self.state = self.LOADED

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
                else:
                    no_tile = pyglet.sprite.Sprite(self.missing_tile.image)
                    no_tile.x = TILE_SIZE * x
                    no_tile.y = -TILE_SIZE * y
                    tiles.append(no_tile)
        return tiles

    def move_left(self):
        self.map_x = max(0, self.map_x - 1024)

    def move_right(self):
        self.map_x = min(1024 * (self.MAP_W - 1), self.map_x + 1024)

    def move_up(self):
        self.map_y = max(0, self.map_y - 1024)

    def move_down(self):
        self.map_y = min(1024 * (self.MAP_H - 1), self.map_y + 1024)

    def draw(self):
        gl.glTranslatef(window.width / 2, window.height // 2, 0)
        gl.glScalef(self.camera.zoom, self.camera.zoom, 1.0)
        gl.glTranslatef(-self.camera.x, self.camera.y, 0)
        OPACITY = 255 # 255 actually, but I'm testing now
        for tile in self.drawable_tiles:
            if tile.opacity < OPACITY:
                tile.opacity = min(OPACITY, int((time.time() - tile.loaded) * OPACITY))
            tile.draw()

        for dot in self.dots:
            dot.draw()

    def load_tile_sprite(self, filename):
        image = load_image(filename)
        image.anchor_x = TILE_SIZE / 2
        image.anchor_y = image.height - TILE_SIZE / 2
        return pyglet.sprite.Sprite(image)

    def load_tile(self, x, y):
        filename = 'tile-%03d-%03d.png' % (y, x)
        sprite = self.load_tile_sprite(filename)
        sprite.loaded = time.time()
        sprite.opacity = 0
        sprite.x = TILE_SIZE * x
        sprite.y = -TILE_SIZE * y
        self.tiles[x, y] = sprite


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
        with gl_matrix():
            self.game.draw_flashes()
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

