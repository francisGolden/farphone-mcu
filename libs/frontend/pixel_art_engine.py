import M5
from M5 import Lcd

C_SOIL_DARK   = 0x4A2500
C_SOIL_LIGHT  = 0x733804
C_STEM_GREEN  = 0x248810
C_LEAF_BRIGHT = 0x5CD632
C_DEAD_STEM   = 0x5A5928
C_DEAD_LEAF   = 0x826C34
C_DEAD_SHADOW = 0x52441E

def draw_tilled_soil(cx, cy):
    Lcd.fillRect(cx - 24, cy + 18, 48, 10, C_SOIL_DARK)
    Lcd.fillRect(cx - 20, cy + 16, 40, 3, C_SOIL_LIGHT)
    Lcd.fillRect(cx - 16, cy + 22, 10, 2, C_SOIL_LIGHT)
    Lcd.fillRect(cx + 8, cy + 20, 12, 2, C_SOIL_LIGHT)

def draw_mystery_sprout(cx, cy, progress_ratio):
    draw_tilled_soil(cx, cy)
    if progress_ratio < 0.35:
        Lcd.fillRect(cx - 1, cy + 8, 3, 10, C_STEM_GREEN)
        Lcd.fillRect(cx - 6, cy + 4, 5, 4, C_LEAF_BRIGHT)
        Lcd.fillRect(cx + 2, cy + 2, 6, 4, C_LEAF_BRIGHT)
    else:
        Lcd.fillRect(cx - 2, cy - 2, 4, 20, C_STEM_GREEN)
        Lcd.fillRect(cx - 10, cy + 6, 8, 4, C_LEAF_BRIGHT)
        Lcd.fillRect(cx + 2, cy + 4, 9, 4, C_LEAF_BRIGHT)
        # Mystery bud container
        Lcd.fillRect(cx - 6, cy - 14, 12, 12, 0x8833AA)
        Lcd.fillRect(cx - 4, cy - 16, 8, 3, 0xBA68C8)
        Lcd.setTextColor(0xFFFFFF, 0x8833AA)
        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setCursor(cx - 3, cy - 14)
        Lcd.print("?")

def draw_withered_crop(cx, cy):
    draw_tilled_soil(cx, cy)
    Lcd.fillRect(cx - 8, cy + 6, 4, 11, C_DEAD_STEM)
    Lcd.fillRect(cx - 6, cy + 2, 4, 4, C_DEAD_STEM)
    Lcd.fillRect(cx - 2, cy - 4, 6, 4, C_DEAD_STEM)
    Lcd.fillRect(cx + 4, cy - 1, 4, 4, C_DEAD_STEM)
    Lcd.fillRect(cx + 6, cy + 2, 6, 5, C_DEAD_LEAF)
    Lcd.fillRect(cx + 12, cy + 14, 5, 3, C_DEAD_LEAF)
    Lcd.fillRect(cx + 16, cy + 15, 3, 2, C_DEAD_SHADOW)

def draw_revealed_plant(cx, cy, rarity_color):
    draw_tilled_soil(cx, cy)
    Lcd.drawCircle(cx, cy - 4, 18, rarity_color)
    Lcd.fillRect(cx - 2, cy - 6, 4, 24, C_STEM_GREEN)
    Lcd.fillRect(cx - 12, cy + 4, 10, 4, C_LEAF_BRIGHT)
    Lcd.fillRect(cx + 2, cy + 2, 11, 4, C_LEAF_BRIGHT)
    Lcd.fillCircle(cx, cy - 8, 9, rarity_color)
    Lcd.fillCircle(cx, cy - 8, 5, 0xFFFFFF)


def draw_chronicle_emblem(cx, top):
    """An open codex with a sprout, drawn on a crisp three-pixel grid."""
    palette = {
        "b": C_SOIL_DARK,
        "s": C_SOIL_LIGHT,
        "p": 0xDDD3BC,
        "h": 0xB89A60,
        "g": C_STEM_GREEN,
        "l": C_LEAF_BRIGHT,
    }
    sprite = (
        ".....ll.ll.....",
        "......lgl......",
        ".......g.......",
        ".sssss.g.sssss.",
        "bsppppsgsppppsb",
        "bphhhpspsphhhpb",
        "bsppppspsppppsb",
        "bphhhpspsphhhpb",
        "bsssssspssssssb",
        ".bbbbbbhbbbbbb.",
    )
    for row, pixels in enumerate(sprite):
        for col, pixel in enumerate(pixels):
            if pixel != ".":
                Lcd.fillRect(cx - 22 + col * 3, top + row * 3,
                             3, 3, palette[pixel])


def draw_chronicle_divider(y):
    """Stepped end caps and a tiled border in the garden palette."""
    for x in range(16, 119, 6):
        Lcd.fillRect(x, y, 4, 2, C_SOIL_LIGHT)
    for x in (7, 123):
        Lcd.fillRect(x, y - 2, 5, 6, C_STEM_GREEN)
        Lcd.fillRect(x + 1, y - 4, 3, 2, C_LEAF_BRIGHT)
