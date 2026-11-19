"""Display helpers: make windows sharp on Windows and fit big videos on screen.
These change only what you SEE. Detection and tracks.csv still use the full-size frame."""
import cv2


def set_dpi_aware():
    """Stop Windows from stretching (and blurring) the video window on scaled screens."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass  # not Windows, or already set: nothing to do


def fit_for_display(frame, max_w=1280, max_h=720):
    """Shrink a big frame so the whole picture fits on screen (never enlarges small ones)."""
    h, w = frame.shape[:2]
    s = min(1.0, max_w / w, max_h / h)
    if s >= 1.0:
        return frame
    return cv2.resize(frame, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)


class ZoomView:
    """Video window with zoom, move and pause. Changes only what you see, never the tracking.

    Mouse:  wheel = zoom at cursor | drag = move picture | click the buttons at top-right
    Keys:   + / -  zoom | 0  reset | W A S D  move | SPACE  pause | N  next frame (when paused) | Q  quit
    """
    MIN_ZOOM, MAX_ZOOM = 1.0, 10.0

    def __init__(self, win, max_w=1280, max_h=720):
        self.win, self.max_w, self.max_h = win, max_w, max_h
        self.zoom, self.cx, self.cy = 1.0, None, None
        self.paused, self.step, self.dragging, self.last = False, False, False, (0, 0)
        self.W = self.H = self.dw = self.dh = 0
        self.vw = self.vh = 1.0
        self.x0 = self.y0 = 0.0
        cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(win, self._mouse)

    # ---- geometry (testable without a window) ----
    def set_frame(self, frame):
        """Work out sizes for this frame."""
        self.H, self.W = frame.shape[:2]
        s = min(1.0, self.max_w / self.W, self.max_h / self.H)
        self.dw, self.dh = int(self.W * s), int(self.H * s)
        if self.cx is None:
            self.cx, self.cy = self.W / 2, self.H / 2
        self._clamp()

    def _clamp(self):
        self.vw, self.vh = self.W / self.zoom, self.H / self.zoom
        self.cx = min(max(self.cx, self.vw / 2), self.W - self.vw / 2)
        self.cy = min(max(self.cy, self.vh / 2), self.H - self.vh / 2)
        self.x0, self.y0 = self.cx - self.vw / 2, self.cy - self.vh / 2

    def zoom_at(self, factor, mx=None, my=None):
        """Zoom in (factor > 1) or out, keeping the point under the cursor fixed."""
        mx = self.dw / 2 if mx is None else mx
        my = self.dh / 2 if my is None else my
        fx, fy = self.x0 + mx * self.vw / self.dw, self.y0 + my * self.vh / self.dh
        self.zoom = min(max(self.zoom * factor, self.MIN_ZOOM), self.MAX_ZOOM)
        vw, vh = self.W / self.zoom, self.H / self.zoom
        self.cx, self.cy = fx - mx * vw / self.dw + vw / 2, fy - my * vh / self.dh + vh / 2
        self._clamp()

    def pan_display(self, dx, dy):
        """Move the picture by dx, dy screen pixels."""
        self.cx -= dx * self.vw / self.dw
        self.cy -= dy * self.vh / self.dh
        self._clamp()

    def reset(self):
        self.zoom, self.cx, self.cy = 1.0, self.W / 2, self.H / 2
        self._clamp()

    # ---- buttons ----
    def _buttons(self):
        labels = ["+", "-", "1:1", "Play" if self.paused else "Pause"]
        widths = [36, 36, 48, 62]
        x, out = self.dw - sum(widths) - 6 * len(widths), []
        for lab, wd in zip(labels, widths):
            out.append((lab, x, 8, wd, 30))
            x += wd + 6
        return out

    def _click_button(self, mx, my):
        for lab, x, y, w, h in self._buttons():
            if x <= mx <= x + w and y <= my <= y + h:
                if lab == "+": self.zoom_at(1.5)
                elif lab == "-": self.zoom_at(1 / 1.5)
                elif lab == "1:1": self.reset()
                else: self.paused = not self.paused
                return True
        return False

    # ---- mouse ----
    def _mouse(self, event, x, y, flags, param):
        if not self.dw:
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            if not self._click_button(x, y):
                self.dragging, self.last = True, (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and self.dragging:
            self.pan_display(x - self.last[0], y - self.last[1])
            self.last = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.dragging = False
        elif event == cv2.EVENT_MOUSEWHEEL:
            try:
                up = cv2.getMouseWheelDelta(flags) > 0
            except Exception:
                up = flags > 0
            self.zoom_at(1.25 if up else 1 / 1.25, x, y)

    # ---- drawing ----
    def render(self, frame):
        """Return the picture to show: the zoomed part of the frame plus buttons and hints."""
        self.set_frame(frame)
        x0, y0 = int(round(self.x0)), int(round(self.y0))
        crop = frame[y0:y0 + int(round(self.vh)), x0:x0 + int(round(self.vw))]
        interp = cv2.INTER_AREA if (crop.shape[1] >= self.dw) else cv2.INTER_CUBIC
        img = cv2.resize(crop, (self.dw, self.dh), interpolation=interp)
        for lab, x, y, w, h in self._buttons():
            cv2.rectangle(img, (x, y), (x + w, y + h), (48, 30, 14), -1)
            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 167, 63), 1)
            cv2.putText(img, lab, (x + 6, y + 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        hint = f"Zoom {self.zoom:.1f}x | wheel/+/-: zoom | drag/WASD: move | SPACE: pause | N: next | 0: reset | Q: quit"
        cv2.rectangle(img, (0, self.dh - 22), (self.dw, self.dh), (48, 30, 14), -1)
        cv2.putText(img, hint, (8, self.dh - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        return img

    def _key(self, k):
        """Handle one key press. Returns False if the user wants to quit."""
        if k == 255 or k < 0:
            return True
        c = chr(k).lower() if k < 128 else ""
        if c == "q": return False
        if c in "+=": self.zoom_at(1.25)
        elif c in "-_": self.zoom_at(1 / 1.25)
        elif c == "0": self.reset()
        elif c == " ": self.paused = not self.paused
        elif c == "n": self.step = True
        elif c == "w": self.pan_display(0, 60)
        elif c == "s": self.pan_display(0, -60)
        elif c == "a": self.pan_display(60, 0)
        elif c == "d": self.pan_display(-60, 0)
        return True

    def show(self, frame):
        """Show one frame. While paused, waits here (zoom and move still work). False = quit."""
        while True:
            cv2.imshow(self.win, self.render(frame))
            if not self._key(cv2.waitKey(20 if self.paused else 1) & 0xFF):
                return False
            if not self.paused:
                return True
            if self.step:
                self.step = False
                return True

    def tick(self, frame):
        """Redraw the window once (about 60 times a second). False = the user pressed Q."""
        cv2.imshow(self.win, self.render(frame))
        return self._key(cv2.waitKey(15) & 0xFF)
