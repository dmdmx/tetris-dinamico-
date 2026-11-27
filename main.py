import json
import math
import os
import random
import sys
import pygame

# Inicialización segura de Pygame y del sistema de audio
pygame.init()
try:
    pygame.mixer.init()
    MIXER_AVAILABLE = True
except pygame.error:
    MIXER_AVAILABLE = False

# Constantes del tablero y ventana
BLOCK_SIZE = 30
GRID_WIDTH = 10
GRID_HEIGHT = 20
BOARD_WIDTH = BLOCK_SIZE * GRID_WIDTH
BOARD_HEIGHT = BLOCK_SIZE * GRID_HEIGHT
SIDEBAR_WIDTH = 250
SCREEN_WIDTH = BOARD_WIDTH + SIDEBAR_WIDTH
SCREEN_HEIGHT = BOARD_HEIGHT

# Tiempos de control (ms)
DAS_DELAY = 150
ARR_INTERVAL = 40
SOFT_DROP_INTERVAL = 45
LOCK_DELAY = 400
MAX_LOCK_RESETS = 12
CLEAR_ANIM_DURATION = 140

# Colores
BLACK = (12, 14, 20)
PANEL_BG = (20, 24, 34)
GRID_LINE = (34, 40, 56)
BORDER_NORMAL = (70, 82, 110)
BORDER_DANGER = (235, 64, 78)
WHITE = (240, 244, 255)
MUTED = (150, 160, 185)
ACCENT = (255, 210, 75)

CYAN = (0, 230, 240)     # I
BLUE = (45, 105, 245)    # J
ORANGE = (255, 145, 35)  # L
YELLOW = (245, 220, 45)  # O
GREEN = (55, 215, 95)    # S
PURPLE = (170, 65, 235)  # T
RED = (240, 60, 75)      # Z

SHAPES = [
    [[1, 1, 1, 1]],
    [[1, 0, 0],
     [1, 1, 1]],
    [[0, 0, 1],
     [1, 1, 1]],
    [[1, 1],
     [1, 1]],
    [[0, 1, 1],
     [1, 1, 0]],
    [[0, 1, 0],
     [1, 1, 1]],
    [[1, 1, 0],
     [0, 1, 1]],
]

COLORS = [CYAN, BLUE, ORANGE, YELLOW, GREEN, PURPLE, RED]

if getattr(sys, "frozen", False):
    RESOURCE_DIR = sys._MEIPASS
    DATA_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "TetrisDinamico")
else:
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = RESOURCE_DIR

HIGHSCORE_FILE = os.path.join(DATA_DIR, "highscore.json")


class Tetromino:
    def __init__(self, shape_idx):
        self.shape_idx = shape_idx
        self.shape = [row[:] for row in SHAPES[shape_idx]]
        self.color = COLORS[shape_idx]
        self.x = GRID_WIDTH // 2 - len(self.shape[0]) // 2
        self.y = 0

    def rotated_shape(self):
        return [
            [self.shape[y][x] for y in range(len(self.shape) - 1, -1, -1)]
            for x in range(len(self.shape[0]))
        ]


class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        angle = random.uniform(0, math.tau)
        speed = random.uniform(90, 280)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - random.uniform(40, 120)
        self.color = color
        self.size = random.randint(4, 8)
        self.life = random.uniform(0.35, 0.65)
        self.max_life = self.life

    def update(self, dt_sec):
        self.vy += 650 * dt_sec  # Gravedad
        self.x += self.vx * dt_sec
        self.y += self.vy * dt_sec
        self.life -= dt_sec

    def draw(self, surface):
        if self.life <= 0:
            return
        alpha = max(0, int(255 * (self.life / self.max_life)))
        s = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        s.fill((*self.color, alpha))
        surface.blit(s, (int(self.x), int(self.y)))


class FloatingText:
    def __init__(self, text, x, y, color=ACCENT):
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.life = 0.95
        self.max_life = 0.95

    def update(self, dt_sec):
        self.y -= 42 * dt_sec
        self.life -= dt_sec

    def draw(self, surface, font):
        if self.life <= 0:
            return
        alpha = max(0, int(255 * (self.life / self.max_life)))
        rendered = font.render(self.text, True, self.color)
        rendered.set_alpha(alpha)
        rect = rendered.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(rendered, rect)


class TetrisGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.canvas = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Tetris Dinámico")
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.Font(None, 42)
        self.font_lg = pygame.font.Font(None, 34)
        self.font_md = pygame.font.Font(None, 26)
        self.font_sm = pygame.font.Font(None, 20)

        # Sonidos de eventos
        self.sounds_muted = False
        self.sound_rotate = self.load_sound("rotate.wav")
        self.sound_lock = self.load_sound("lock.wav")
        self.sound_clear = self.load_sound("clear.wav")
        self.sound_move = self.load_sound("move.wav")
        self.sound_fall = self.load_sound("fall.wav")
        self.sound_game_over = self.load_sound("game_over.wav")

        self.high_score = self.load_high_score()
        self.reset()

    def load_sound(self, filename):
        if not MIXER_AVAILABLE:
            return None
        candidates = [
            os.path.join(RESOURCE_DIR, "assets", "sounds", filename),
        ]
        if getattr(sys, "frozen", False):
            candidates.extend([
                os.path.join(RESOURCE_DIR, "..", "Resources", "assets", "sounds", filename),
                os.path.join(os.path.dirname(sys.executable), "..", "Resources", "assets", "sounds", filename),
            ])

        sound_path = next((path for path in candidates if os.path.exists(path)), None)
        if sound_path is None:
            return None
        try:
            return pygame.mixer.Sound(sound_path)
        except Exception:
            return None

    def play_sound(self, sound):
        if sound and not self.sounds_muted:
            sound.play()

    def load_high_score(self):
        try:
            with open(HIGHSCORE_FILE, "r", encoding="utf-8") as f:
                return int(json.load(f).get("high_score", 0))
        except Exception:
            return 0

    def save_high_score(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(HIGHSCORE_FILE, "w", encoding="utf-8") as f:
                json.dump({"high_score": self.high_score}, f)
        except Exception:
            pass

    def reset(self):
        self.grid = [[BLACK for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.bag = []
        self.next_queue = [self.draw_from_bag() for _ in range(3)]
        self.current_piece = None
        self.hold_piece = None
        self.can_hold = True

        self.score = 0
        self.lines_total = 0
        self.level = 1
        self.combo = 0
        self.back_to_back = False
        self.fall_speed = self.compute_fall_speed()

        self.fall_timer = 0
        self.lock_timer = 0
        self.lock_resets = 0

        self.held_dir = 0
        self.das_timer = 0
        self.arr_timer = 0
        self.soft_drop_timer = 0

        self.clearing_rows = []
        self.clear_anim_timer = 0
        self.particles = []
        self.floating_texts = []
        self.shake_timer = 0
        self.shake_intensity = 0
        self.elapsed_ms = 0

        self.paused = False
        self.game_over = False

        self.spawn_next_piece()

    def compute_fall_speed(self):
        return max(75, int(550 * (0.85 ** (self.level - 1))))

    def draw_from_bag(self):
        if not self.bag:
            self.bag = list(range(len(SHAPES)))
            random.shuffle(self.bag)
        return Tetromino(self.bag.pop())

    def spawn_next_piece(self):
        self.current_piece = self.next_queue.pop(0)
        self.next_queue.append(self.draw_from_bag())
        self.can_hold = True
        self.fall_timer = 0
        self.lock_timer = 0
        self.lock_resets = 0

        if not self.valid_move(self.current_piece.shape, self.current_piece.x, self.current_piece.y):
            self.trigger_game_over()

    def trigger_game_over(self):
        if self.game_over:
            return
        self.game_over = True
        self.play_sound(self.sound_game_over)
        if self.score > self.high_score:
            self.high_score = self.score
            self.save_high_score()

    def valid_move(self, shape, x, y):
        for i, row in enumerate(shape):
            for j, cell in enumerate(row):
                if cell:
                    new_x = x + j
                    new_y = y + i
                    if new_x < 0 or new_x >= GRID_WIDTH or new_y >= GRID_HEIGHT:
                        return False
                    if new_y >= 0 and self.grid[new_y][new_x] != BLACK:
                        return False
        return True

    def is_grounded(self):
        if not self.current_piece:
            return False
        return not self.valid_move(
            self.current_piece.shape,
            self.current_piece.x,
            self.current_piece.y + 1,
        )

    def reset_lock_if_needed(self):
        if self.is_grounded() and self.lock_resets < MAX_LOCK_RESETS:
            self.lock_timer = 0
            self.lock_resets += 1

    def move_horizontal(self, dx):
        if not self.current_piece:
            return False
        if self.valid_move(self.current_piece.shape, self.current_piece.x + dx, self.current_piece.y):
            self.current_piece.x += dx
            self.play_sound(self.sound_move)
            self.reset_lock_if_needed()
            return True
        return False

    def move_down(self, manual=False):
        if not self.current_piece:
            return False
        if self.valid_move(self.current_piece.shape, self.current_piece.x, self.current_piece.y + 1):
            self.current_piece.y += 1
            self.fall_timer = 0
            self.lock_timer = 0
            if manual:
                self.add_score(1)
                self.play_sound(self.sound_move)
            else:
                self.play_sound(self.sound_fall)
            return True
        return False

    def rotate_piece(self):
        if not self.current_piece or self.current_piece.shape_idx == 3:
            return
        rotated = self.current_piece.rotated_shape()
        # Wall kicks simples para poder girar pegado a bordes o bloques
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1)):
            if self.valid_move(rotated, self.current_piece.x + dx, self.current_piece.y + dy):
                self.current_piece.shape = rotated
                self.current_piece.x += dx
                self.current_piece.y += dy
                self.play_sound(self.sound_rotate)
                self.reset_lock_if_needed()
                return

    def get_ghost_y(self):
        y = self.current_piece.y
        while self.valid_move(self.current_piece.shape, self.current_piece.x, y + 1):
            y += 1
        return y

    def hard_drop(self):
        if not self.current_piece:
            return
        ghost_y = self.get_ghost_y()
        distance = ghost_y - self.current_piece.y
        self.current_piece.y = ghost_y
        self.add_score(distance * 2)
        self.trigger_shake(duration=90, intensity=3)
        self.lock_piece()

    def hold_current_piece(self):
        if not self.current_piece or not self.can_hold:
            return
        self.can_hold = False
        held_idx = self.current_piece.shape_idx
        if self.hold_piece is None:
            self.hold_piece = Tetromino(held_idx)
            self.spawn_next_piece()
            self.can_hold = False
        else:
            swapped = Tetromino(self.hold_piece.shape_idx)
            self.hold_piece = Tetromino(held_idx)
            self.current_piece = swapped
            self.fall_timer = 0
            self.lock_timer = 0
            self.lock_resets = 0
            if not self.valid_move(self.current_piece.shape, self.current_piece.x, self.current_piece.y):
                self.trigger_game_over()
        self.play_sound(self.sound_move)

    def add_score(self, points):
        self.score += points
        if self.score > self.high_score:
            self.high_score = self.score

    def trigger_shake(self, duration, intensity):
        self.shake_timer = max(self.shake_timer, duration)
        self.shake_intensity = max(self.shake_intensity, intensity)

    def lock_piece(self):
        for i, row in enumerate(self.current_piece.shape):
            for j, cell in enumerate(row):
                if cell:
                    gy = self.current_piece.y + i
                    gx = self.current_piece.x + j
                    if gy < 0:
                        self.trigger_game_over()
                        return
                    self.grid[gy][gx] = self.current_piece.color

        self.play_sound(self.sound_lock)
        self.current_piece = None

        full_rows = [
            i for i, row in enumerate(self.grid)
            if all(cell != BLACK for cell in row)
        ]

        if full_rows:
            self.start_line_clear(full_rows)
        else:
            self.combo = 0
            self.spawn_next_piece()

    def start_line_clear(self, full_rows):
        count = len(full_rows)
        self.clearing_rows = full_rows
        self.clear_anim_timer = CLEAR_ANIM_DURATION

        # Generar partículas en cada bloque de las filas completadas
        for row_idx in full_rows:
            for col_idx in range(GRID_WIDTH):
                color = self.grid[row_idx][col_idx]
                px = col_idx * BLOCK_SIZE + BLOCK_SIZE // 2
                py = row_idx * BLOCK_SIZE + BLOCK_SIZE // 2
                for _ in range(3):
                    self.particles.append(Particle(px, py, color))

        # Puntuación, combo y back-to-back
        self.combo += 1
        base_points = [0, 100, 300, 500, 800][count] * self.level
        if count == 4 and self.back_to_back:
            base_points = int(base_points * 1.5)
        self.back_to_back = (count == 4)

        combo_bonus = 50 * (self.combo - 1) * self.level if self.combo > 1 else 0
        total_gain = base_points + combo_bonus
        self.add_score(total_gain)

        prev_level = self.level
        self.lines_total += count
        self.level = 1 + self.lines_total // 10
        self.fall_speed = self.compute_fall_speed()

        # Textos flotantes y efecto de cámara
        mid_y = (sum(full_rows) / count) * BLOCK_SIZE + BLOCK_SIZE // 2
        if count == 4:
            label = f"TETRIS! +{total_gain}"
            self.trigger_shake(duration=220, intensity=7)
        else:
            label = f"+{total_gain}"
            self.trigger_shake(duration=110, intensity=3)

        self.floating_texts.append(FloatingText(label, BOARD_WIDTH // 2, mid_y, ACCENT))
        if self.combo > 1:
            self.floating_texts.append(
                FloatingText(f"COMBO x{self.combo}!", BOARD_WIDTH // 2, mid_y - 26, CYAN)
            )
        if self.level > prev_level:
            self.floating_texts.append(
                FloatingText(f"NIVEL {self.level}!", BOARD_WIDTH // 2, BOARD_HEIGHT // 2, GREEN)
            )

        self.play_sound(self.sound_clear)

    def finish_line_clear(self):
        cleared_set = set(self.clearing_rows)
        remaining = [row for i, row in enumerate(self.grid) if i not in cleared_set]
        empty_rows = [[BLACK for _ in range(GRID_WIDTH)] for _ in range(len(cleared_set))]
        self.grid = empty_rows + remaining
        self.clearing_rows = []
        self.spawn_next_piece()

    def update(self, dt):
        self.elapsed_ms += dt
        dt_sec = dt / 1000.0

        # Efectos visuales siempre se actualizan aunque estemos limpiando líneas
        for p in self.particles:
            p.update(dt_sec)
        self.particles = [p for p in self.particles if p.life > 0]

        for ft in self.floating_texts:
            ft.update(dt_sec)
        self.floating_texts = [ft for ft in self.floating_texts if ft.life > 0]

        if self.shake_timer > 0:
            self.shake_timer = max(0, self.shake_timer - dt)
            if self.shake_timer == 0:
                self.shake_intensity = 0

        if self.paused or self.game_over:
            return

        if self.clearing_rows:
            self.clear_anim_timer -= dt
            if self.clear_anim_timer <= 0:
                self.finish_line_clear()
            return

        if not self.current_piece:
            return

        # Movimiento lateral continuo (DAS + ARR)
        keys = pygame.key.get_pressed()
        if self.held_dir == -1 and keys[pygame.K_LEFT]:
            self.das_timer += dt
            if self.das_timer >= DAS_DELAY:
                self.arr_timer += dt
                while self.arr_timer >= ARR_INTERVAL:
                    self.arr_timer -= ARR_INTERVAL
                    if not self.move_horizontal(-1):
                        break
        elif self.held_dir == 1 and keys[pygame.K_RIGHT]:
            self.das_timer += dt
            if self.das_timer >= DAS_DELAY:
                self.arr_timer += dt
                while self.arr_timer >= ARR_INTERVAL:
                    self.arr_timer -= ARR_INTERVAL
                    if not self.move_horizontal(1):
                        break

        # Soft drop continuo al mantener ↓
        if keys[pygame.K_DOWN]:
            self.soft_drop_timer += dt
            while self.soft_drop_timer >= SOFT_DROP_INTERVAL:
                self.soft_drop_timer -= SOFT_DROP_INTERVAL
                if not self.move_down(manual=True):
                    break

        # Caída automática y lock delay
        if self.is_grounded():
            self.lock_timer += dt
            if self.lock_timer >= LOCK_DELAY:
                self.lock_piece()
        else:
            self.fall_timer += dt
            if self.fall_timer >= self.fall_speed:
                self.fall_timer -= self.fall_speed
                self.move_down(manual=False)

    def draw_block(self, surface, px, py, color, size=BLOCK_SIZE):
        rect = pygame.Rect(px, py, size, size)
        pygame.draw.rect(surface, color, rect)

        highlight = tuple(min(255, c + 55) for c in color)
        shadow = tuple(max(0, c - 70) for c in color)
        bevel = max(2, size // 8)

        pygame.draw.line(surface, highlight, (px, py), (px + size - 1, py), bevel)
        pygame.draw.line(surface, highlight, (px, py), (px, py + size - 1), bevel)
        pygame.draw.line(surface, shadow, (px, py + size - 1), (px + size - 1, py + size - 1), bevel)
        pygame.draw.line(surface, shadow, (px + size - 1, py), (px + size - 1, py + size - 1), bevel)
        pygame.draw.rect(surface, BLACK, rect, 1)

    def draw_grid(self, surface):
        clearing_set = set(self.clearing_rows)
        for i in range(GRID_HEIGHT):
            for j in range(GRID_WIDTH):
                px = j * BLOCK_SIZE
                py = i * BLOCK_SIZE
                if i in clearing_set:
                    pygame.draw.rect(surface, WHITE, (px, py, BLOCK_SIZE, BLOCK_SIZE))
                elif self.grid[i][j] != BLACK:
                    self.draw_block(surface, px, py, self.grid[i][j])
                else:
                    pygame.draw.rect(surface, GRID_LINE, (px, py, BLOCK_SIZE, BLOCK_SIZE), 1)

        # Borde de peligro pulsante si la pila alcanza las 4 filas superiores
        danger = any(self.grid[y][x] != BLACK for y in range(4) for x in range(GRID_WIDTH))
        if danger and not self.game_over and (self.elapsed_ms // 250) % 2 == 0:
            border_color = BORDER_DANGER
        else:
            border_color = BORDER_NORMAL
        pygame.draw.rect(surface, border_color, (0, 0, BOARD_WIDTH, BOARD_HEIGHT), 2)

    def draw_ghost_piece(self, surface):
        if not self.current_piece:
            return
        ghost_y = self.get_ghost_y()
        if ghost_y == self.current_piece.y:
            return
        fill_surf = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE), pygame.SRCALPHA)
        fill_surf.fill((*self.current_piece.color, 45))

        for i, row in enumerate(self.current_piece.shape):
            for j, cell in enumerate(row):
                if cell:
                    gy = ghost_y + i
                    if gy >= 0:
                        px = (self.current_piece.x + j) * BLOCK_SIZE
                        py = gy * BLOCK_SIZE
                        surface.blit(fill_surf, (px, py))
                        pygame.draw.rect(
                            surface,
                            self.current_piece.color,
                            (px, py, BLOCK_SIZE, BLOCK_SIZE),
                            1,
                        )

    def draw_current_piece(self, surface):
        if not self.current_piece:
            return
        for i, row in enumerate(self.current_piece.shape):
            for j, cell in enumerate(row):
                if cell:
                    gy = self.current_piece.y + i
                    if gy >= 0:
                        px = (self.current_piece.x + j) * BLOCK_SIZE
                        py = gy * BLOCK_SIZE
                        self.draw_block(surface, px, py, self.current_piece.color)

    def draw_mini_piece(self, surface, piece, box_rect, size=20):
        if not piece:
            return
        rows = len(piece.shape)
        cols = len(piece.shape[0])
        total_w = cols * size
        total_h = rows * size
        start_x = box_rect.x + (box_rect.width - total_w) // 2
        start_y = box_rect.y + (box_rect.height - total_h) // 2

        for i, row in enumerate(piece.shape):
            for j, cell in enumerate(row):
                if cell:
                    self.draw_block(
                        surface,
                        start_x + j * size,
                        start_y + i * size,
                        piece.color,
                        size=size,
                    )

    def draw_sidebar(self, surface):
        panel_rect = pygame.Rect(BOARD_WIDTH, 0, SIDEBAR_WIDTH, SCREEN_HEIGHT)
        pygame.draw.rect(surface, PANEL_BG, panel_rect)

        x0 = BOARD_WIDTH + 20
        box_w = SIDEBAR_WIDTH - 40

        # Reserva (Hold)
        surface.blit(self.font_md.render("RESERVA (C)", True, MUTED), (x0, 14))
        hold_box = pygame.Rect(x0, 38, box_w, 64)
        pygame.draw.rect(surface, BLACK, hold_box, border_radius=6)
        pygame.draw.rect(surface, BORDER_NORMAL, hold_box, 1, border_radius=6)
        self.draw_mini_piece(surface, self.hold_piece, hold_box, size=18)

        # Cola de 3 siguientes piezas
        surface.blit(self.font_md.render("SIGUIENTES", True, MUTED), (x0, 116))
        next_box = pygame.Rect(x0, 140, box_w, 195)
        pygame.draw.rect(surface, BLACK, next_box, border_radius=6)
        pygame.draw.rect(surface, BORDER_NORMAL, next_box, 1, border_radius=6)
        for idx, piece in enumerate(self.next_queue):
            slot = pygame.Rect(x0, 145 + idx * 62, box_w, 58)
            self.draw_mini_piece(surface, piece, slot, size=18)

        # Estadísticas
        stats_y = 352
        stats = [
            ("PUNTAJE", f"{self.score}", WHITE),
            ("RÉCORD", f"{self.high_score}", ACCENT),
            ("NIVEL", f"{self.level}", CYAN),
            ("LÍNEAS", f"{self.lines_total}", GREEN),
        ]
        for label, value, color in stats:
            surface.blit(self.font_sm.render(label, True, MUTED), (x0, stats_y))
            val_surf = self.font_lg.render(value, True, color)
            surface.blit(val_surf, (x0, stats_y + 15))
            stats_y += 45

        # Controles rápidos
        controls_y = 538
        hints = [
            "Espacio: Caída rápida",
            "C / Shift: Reserva",
            "P: Pausa | R: Reiniciar",
            f"M: {'Activar' if self.sounds_muted else 'Silenciar'} sonido",
        ]
        for hint in hints:
            surface.blit(self.font_sm.render(hint, True, MUTED), (x0, controls_y))
            controls_y += 18

    def draw_overlay(self, surface, title, lines, title_color=WHITE):
        overlay = pygame.Surface((BOARD_WIDTH, BOARD_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 12, 18, 195))
        surface.blit(overlay, (0, 0))

        t_surf = self.font_title.render(title, True, title_color)
        surface.blit(t_surf, t_surf.get_rect(center=(BOARD_WIDTH // 2, BOARD_HEIGHT // 2 - 50)))

        for idx, line in enumerate(lines):
            l_surf = self.font_md.render(line, True, WHITE)
            surface.blit(
                l_surf,
                l_surf.get_rect(center=(BOARD_WIDTH // 2, BOARD_HEIGHT // 2 + idx * 32)),
            )

    def draw(self):
        self.canvas.fill(BLACK)
        self.draw_grid(self.canvas)
        self.draw_ghost_piece(self.canvas)
        self.draw_current_piece(self.canvas)

        for p in self.particles:
            p.draw(self.canvas)
        for ft in self.floating_texts:
            ft.draw(self.canvas, self.font_lg)

        if self.paused and not self.game_over:
            self.draw_overlay(self.canvas, "PAUSA", ["[P] o [Esc] Continuar", "[R] Reiniciar"], CYAN)
        elif self.game_over:
            self.draw_overlay(
                self.canvas,
                "GAME OVER",
                [f"Puntaje: {self.score}", f"Récord: {self.high_score}", "[R] Jugar de nuevo"],
                BORDER_DANGER,
            )

        self.draw_sidebar(self.canvas)

        offset_x = 0
        offset_y = 0
        if self.shake_timer > 0:
            offset_x = random.randint(-self.shake_intensity, self.shake_intensity)
            offset_y = random.randint(-self.shake_intensity, self.shake_intensity)

        self.screen.fill(BLACK)
        self.screen.blit(self.canvas, (offset_x, offset_y))
        pygame.display.flip()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_m:
                    self.sounds_muted = not self.sounds_muted
                    if not self.sounds_muted:
                        self.play_sound(self.sound_move)
                    continue

                if self.game_over:
                    if event.key == pygame.K_r:
                        self.reset()
                    elif event.key == pygame.K_ESCAPE:
                        return False
                    continue

                if event.key in (pygame.K_p, pygame.K_ESCAPE):
                    self.paused = not self.paused
                    continue

                if event.key == pygame.K_r and self.paused:
                    self.reset()
                    continue

                if self.paused or self.clearing_rows or not self.current_piece:
                    continue

                if event.key == pygame.K_LEFT:
                    self.move_horizontal(-1)
                    self.held_dir = -1
                    self.das_timer = 0
                    self.arr_timer = 0
                elif event.key == pygame.K_RIGHT:
                    self.move_horizontal(1)
                    self.held_dir = 1
                    self.das_timer = 0
                    self.arr_timer = 0
                elif event.key == pygame.K_DOWN:
                    self.move_down(manual=True)
                    self.soft_drop_timer = 0
                elif event.key in (pygame.K_UP, pygame.K_x):
                    self.rotate_piece()
                elif event.key == pygame.K_SPACE:
                    self.hard_drop()
                elif event.key in (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT):
                    self.hold_current_piece()

            elif event.type == pygame.KEYUP:
                keys = pygame.key.get_pressed()
                if event.key == pygame.K_LEFT and self.held_dir == -1:
                    self.held_dir = 1 if keys[pygame.K_RIGHT] else 0
                    self.das_timer = 0
                    self.arr_timer = 0
                elif event.key == pygame.K_RIGHT and self.held_dir == 1:
                    self.held_dir = -1 if keys[pygame.K_LEFT] else 0
                    self.das_timer = 0
                    self.arr_timer = 0

        return True

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60)
            running = self.handle_events()
            self.update(dt)
            self.draw()

        if self.score > self.high_score:
            self.high_score = self.score
        self.save_high_score()
        pygame.quit()


if __name__ == "__main__":
    game = TetrisGame()
    game.run()
