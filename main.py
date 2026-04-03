import builtins
import contextlib

import glfw
import sexpdata
import skia
from kiwisolver import Solver, Variable
from OpenGL import GL

WIDTH, HEIGHT = 640, 480

window_width = Variable("window_width")
window_height = Variable("window_height")

keyword_map = {
    "window_width": window_width,
    "window_height": window_height,
    "page": "page",
    "rect": "rect",
    "rgba": "rgba",
    "/": "/",
}

# probably need an abstract "elem" class all others inherit from


class Page:
    def __init__(self):
        self.children = []
        self.color = (255, 255, 255, 255)

    def assign_value(self, var, iterator):
        param_func = {
            ":color": lambda v: setattr(self, "color", process(v)),
            ":children": lambda v: setattr(
                self, "children", [process(iter(i)) for i in iter(next(v))]
            ),
        }.get(var, None)

        if param_func is None:
            exit()
        param_func(iterator)


class Rect:
    def __init__(self):
        elem_id = id(self)
        # these should all have a unique id attached to them
        self.rect_width = Variable(f"rect_width{elem_id}")
        self.rect_height = Variable(f"rect_height{elem_id}")
        self.rect_left = Variable(f"rect_left{elem_id}")
        self.rect_top = Variable(f"rect_top{elem_id}")
        self.color = (255, 255, 255, 255)
        self.constraints = []

    def assign_value(self, var, iterator):
        param = {
            ":width": self.rect_width,
            ":height": self.rect_height,
            ":top": self.rect_top,
            ":left": self.rect_left,
        }.get(var, None)

        val = process(iterator)

        if param is None:  # non-constraint attribute
            param_func = {":color": lambda v: setattr(self, "color", v)}.get(var, None)
            if param_func is None:
                exit()
            param_func(val)
        else:
            self.constraints.append(param == val)


def process(iterator):
    val = next(iterator, None)
    if val is None:
        exit()

    print(val)

    match type(val):
        case builtins.int:
            return val
        case builtins.float:
            return val
        case sexpdata.Symbol:
            real_val = keyword_map.get(val.value(), None)

            match real_val:
                # perhaps these should be lambda functions or something
                case "page":
                    while True:
                        cur = next(iterator, None)
                        if cur is None:
                            break

                        page.assign_value(cur.value(), iterator)
                case "rect":
                    elem = Rect()

                    while True:
                        cur = next(iterator, None)
                        if cur is None:
                            break

                        elem.assign_value(cur.value(), iterator)

                    for cn in elem.constraints:
                        solver.addConstraint(cn)

                    return elem
                case "/":
                    val1 = process(iterator)
                    val2 = process(iterator)
                    return val1 / val2
                case "rgba":
                    val1 = process(iterator)
                    val2 = process(iterator)
                    val3 = process(iterator)
                    val4 = int(process(iterator) * 255)
                    return (val1, val2, val3, val4)
                case _:
                    # a variable
                    return real_val
        case builtins.list:
            print("is list")
            nested = iter(val)
            return process(nested)
        case _:
            exit()


def kiwi_to_skia():
    global window_width
    global window_height

    solver.suggestValue(window_width, WIDTH)
    solver.suggestValue(window_height, HEIGHT)

    solver.updateVariables()

    with skia_surface(window) as surface:
        with surface as canvas:
            rect = skia.Rect(0, 0, WIDTH, HEIGHT)
            paint = skia.Paint(Color=skia.Color(*page.color))
            canvas.drawRect(rect, paint)

            # this should iterate through a list/tree of structures or class instances that tell it what to draw
            for elem in page.children:
                rect = skia.Rect(
                    elem.rect_left.value(),
                    elem.rect_top.value(),
                    elem.rect_width.value(),
                    elem.rect_height.value(),
                )
                paint = skia.Paint(Color=skia.Color(*elem.color))
                canvas.drawRect(rect, paint)
        surface.flushAndSubmit()
        glfw.swap_buffers(window)


def window_size_callback(window, width, height):
    global WIDTH, HEIGHT
    WIDTH, HEIGHT = width, height

    kiwi_to_skia()


@contextlib.contextmanager
def glfw_window():
    if not glfw.init():
        raise RuntimeError("glfw.init() failed")
    glfw.window_hint(glfw.STENCIL_BITS, 8)
    window = glfw.create_window(WIDTH, HEIGHT, "", None, None)
    glfw.make_context_current(window)

    glfw.set_window_size_callback(window, window_size_callback)

    yield window
    glfw.terminate()


@contextlib.contextmanager
def skia_surface(window):
    context = skia.GrDirectContext.MakeGL()
    (fb_width, fb_height) = glfw.get_framebuffer_size(window)
    backend_render_target = skia.GrBackendRenderTarget(
        fb_width,
        fb_height,
        0,  # sampleCnt
        0,  # stencilBits
        skia.GrGLFramebufferInfo(0, GL.GL_RGBA8),
    )
    surface = skia.Surface.MakeFromBackendRenderTarget(
        context,
        backend_render_target,
        skia.kBottomLeft_GrSurfaceOrigin,
        skia.kRGBA_8888_ColorType,
        skia.ColorSpace.MakeSRGB(),
    )
    assert surface is not None
    yield surface
    context.abandonContext()


page = Page()

sexp = r"""(page
        :color (rgba 200 207 230 1.0)
        :children (
            (rect
                :width (/ window_width 2) :height (/ window_height 2)
                :top 0 :left 10
                :color (rgba 0 102 204 1)
            )
            (rect
                :width (/ window_width 3) :height (/ window_height 3)
                :top 50 :left 20
                :color (rgba 255 153 51 .7)
            )
        )
    )"""

output = iter(sexpdata.loads(sexp))

solver = Solver()

solver.addEditVariable(window_width, "strong")
solver.addEditVariable(window_height, "strong")

process(iter(output))

with glfw_window() as window:
    GL.glClear(GL.GL_COLOR_BUFFER_BIT)

    kiwi_to_skia()

    while glfw.get_key(
        window, glfw.KEY_ESCAPE
    ) != glfw.PRESS and not glfw.window_should_close(window):
        glfw.wait_events()
