from PIL import Image, ImageDraw

SIZE = 512
BG = (5, 8, 10, 255)  # #05080a
GRAD_START = (94, 234, 212)  # #5eead4
GRAD_END = (8, 145, 178)  # #0891b2

# --- fondo: cuadrado redondeado oscuro ---
canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
bg_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
bg_draw = ImageDraw.Draw(bg_layer)
bg_draw.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=90, fill=BG)
canvas.alpha_composite(bg_layer)

# --- gradiente diagonal para el trazo turquesa ---
gradient = Image.new("RGB", (SIZE, SIZE))
gpix = gradient.load()
for y in range(SIZE):
    for x in range(SIZE):
        t = (x + y) / (2 * SIZE)
        r = int(GRAD_START[0] + (GRAD_END[0] - GRAD_START[0]) * t)
        g = int(GRAD_START[1] + (GRAD_END[1] - GRAD_START[1]) * t)
        b = int(GRAD_START[2] + (GRAD_END[2] - GRAD_START[2]) * t)
        gpix[x, y] = (r, g, b)

# --- mascara: dibujo el isotipo (casa + lupa) en blanco ---
mask = Image.new("L", (SIZE, SIZE), 0)
mdraw = ImageDraw.Draw(mask)

STROKE = 24
CAP_R = STROKE // 2


def linea(dibujo, p1, p2, ancho=STROKE, color=255):
    dibujo.line([p1, p2], fill=color, width=ancho, joint="curve")
    r = ancho // 2
    dibujo.ellipse([p1[0] - r, p1[1] - r, p1[0] + r, p1[1] + r], fill=color)
    dibujo.ellipse([p2[0] - r, p2[1] - r, p2[0] + r, p2[1] + r], fill=color)


# cuerpo de la casa (rectangulo con base redondeada) -- se dibuja primero
body_left, body_right = 192, 320
body_top, body_bottom = 240, 336
mdraw.rounded_rectangle(
    [body_left, body_top, body_right, body_bottom],
    radius=14,
    outline=255,
    width=STROKE,
)

# techo (tejado a dos aguas), se superpone al borde superior del cuerpo
techo_izq = (160, 256)
techo_pico = (256, 168)
techo_der = (352, 256)
linea(mdraw, techo_izq, techo_pico)
linea(mdraw, techo_pico, techo_der)

# --- lupa: circulo hueco (knockout) + anillo + mango ---
lupa_centro = (292, 292)
lupa_r = 32
knockout_r = lupa_r + 20

# "vacía" lo que haya debajo del circulo de la lupa (incluida la casa)
mdraw.ellipse(
    [lupa_centro[0] - knockout_r, lupa_centro[1] - knockout_r,
     lupa_centro[0] + knockout_r, lupa_centro[1] + knockout_r],
    fill=0,
)

anillo_mask = Image.new("L", (SIZE, SIZE), 0)
adraw = ImageDraw.Draw(anillo_mask)
ring_w = 14
adraw.ellipse(
    [lupa_centro[0] - lupa_r, lupa_centro[1] - lupa_r,
     lupa_centro[0] + lupa_r, lupa_centro[1] + lupa_r],
    outline=255, width=ring_w,
)
linea(adraw, (315, 315), (338, 338), ancho=ring_w)

# combinamos: cuerpo de la casa+techo (con el hueco) + anillo/mango de la lupa
mask = Image.eval(mask, lambda v: v)
final_mask = Image.new("L", (SIZE, SIZE), 0)
final_mask.paste(mask, (0, 0))
final_mask = Image.composite(anillo_mask, final_mask, anillo_mask)

# --- aplicamos el gradiente a traves de la mascara y componemos sobre el fondo ---
icono_color = Image.new("RGBA", (SIZE, SIZE))
icono_color.paste(gradient, (0, 0))
icono_color.putalpha(final_mask)

canvas.alpha_composite(icono_color)

canvas.convert("RGB").save("logo_compratucasa.png")
print("guardado logo_compratucasa.png", canvas.size)
