"""
assets.py
Loader centralizado de imagens, sons e fontes.
Todos os outros módulos importam daqui — nunca carregam arquivos direto.
"""
import os
import unicodedata
import pygame
from src.emoji_renderer import emoji_surface

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _path(*parts):
    return os.path.join(_BASE, *parts)

# ── Imagens ──────────────────────────────────────────────────────────────────
def load_image(path: str, size: tuple = None, alpha: bool = False) -> pygame.Surface:
    """Carrega imagem e redimensiona se size=(w,h) for fornecido."""
    full = _path(path)
    img = pygame.image.load(full).convert_alpha() if alpha else pygame.image.load(full).convert()
    if size:
        img = pygame.transform.smoothscale(img, size)
    return img

# ── Fontes ────────────────────────────────────────────────────────────────────
_font_cache: dict = {}

def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("Arial", size, bold=bold)
    return _font_cache[key]

def font_path(rel_path: str, size: int) -> pygame.font.Font:
    """Carrega fonte customizada de assets/fonts/."""
    key = (rel_path, size)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.Font(_path("assets", "fonts", rel_path), size)
    return _font_cache[key]

# ── Helpers de texto ──────────────────────────────────────────────────────────
def render_text(text: str, size: int, color, bold: bool = False,
                shadow: bool = False, shadow_color=(0,0,0)) -> pygame.Surface:
    f = font(size, bold)
    if shadow:
        sh = f.render(text, True, shadow_color)
        base = f.render(text, True, color)
        surf = pygame.Surface((base.get_width()+2, base.get_height()+2), pygame.SRCALPHA)
        surf.blit(sh, (2, 2))
        surf.blit(base, (0, 0))
        return surf
    return f.render(text, True, color)


def _is_emoji_char(ch: str) -> bool:
    """
    Heurística para separar emoji de texto comum: caracteres da
    categoria Unicode 'So' (Symbol, other) são emoji/símbolos na
    prática (▶ ℹ ✕ 🧍 👥 🧩 🔍 💡 ⚙ etc.), enquanto letras, números e
    pontuação comum (incluindo — e ...) ficam em outras categorias e
    continuam sendo desenhados pela fonte normal.
    Seletores de variação (ex.: o ️ depois de ⚙) e ZWJ são tratados como
    parte do emoji anterior, nunca como um "token" próprio.
    """
    if ch in ("\ufe0f", "\ufe0e", "\u200d"):
        return True
    return unicodedata.category(ch) == "So"


def render_mixed(text: str, size: int, color, bold: bool = False,
                  shadow: bool = False, shadow_color=(0, 0, 0)) -> pygame.Surface:
    """
    Como render_text(), mas reconhece emojis dentro da string e os
    desenha coloridos via emoji_renderer (o mesmo usado para os objetos
    e o recipiente nas fases), em vez de deixar a fonte do sistema
    desenhar um quadradinho "tofu" no lugar.

    Texto comum (incluindo acentos, espaços e pontuação) continua
    sendo desenhado pela fonte normal — só os trechos reconhecidos como
    emoji passam pelo renderizador colorido. Pode ser usado como
    substituto direto de render_text() em qualquer lugar.
    """
    if not text:
        return pygame.Surface((0, 0), pygame.SRCALPHA)

    # Agrupa a string em blocos consecutivos do mesmo tipo (emoji vs texto)
    chunks: list[tuple[bool, str]] = []
    cur_is_emoji = _is_emoji_char(text[0])
    cur = text[0]
    for ch in text[1:]:
        is_emoji = _is_emoji_char(ch)
        if is_emoji == cur_is_emoji:
            cur += ch
        else:
            chunks.append((cur_is_emoji, cur))
            cur, cur_is_emoji = ch, is_emoji
    chunks.append((cur_is_emoji, cur))

    # Emoji fica visualmente um pouco maior que o texto ao redor (senão
    # parece pequeno demais comparado à altura da fonte normal).
    emoji_size = max(1, int(size * 1.2))

    pieces: list[pygame.Surface] = []
    for is_emoji, chunk in chunks:
        if is_emoji:
            pieces.append(emoji_surface(chunk, size=emoji_size))
        else:
            pieces.append(render_text(chunk, size, color, bold=bold,
                                      shadow=shadow, shadow_color=shadow_color))

    total_w = sum(p.get_width() for p in pieces)
    total_h = max(p.get_height() for p in pieces)
    combined = pygame.Surface((total_w, total_h), pygame.SRCALPHA)
    x = 0
    for surf in pieces:
        y = (total_h - surf.get_height()) // 2   # centraliza verticalmente
        combined.blit(surf, (x, y))
        x += surf.get_width()
    return combined



# ══════════════════════════════════════════════════════════════════════════════
# Arte do modo história: cache, placeholder, fundos "cover" e personagens
# ══════════════════════════════════════════════════════════════════════════════
IMAGES_DIR = os.path.join("assets", "images")

# Cores base da UI desenhada em código
C_UI_DARK  = (0x14, 0x22, 0x41)   # #142241
C_UI_LIGHT = (0xD9, 0xD9, 0xD9)   # #D9D9D9

# Arquivos exportados DEITADOS (cabeça à esquerda, pés à direita).
# Quando a arte for reexportada em pé, basta remover o prefixo daqui.
ROTATED_PREFIXES = ("menino/corpo_", "mae/corpo_", "lipe/corpo_")

# Pose usada como referência de TAMANHO de cada personagem. Todas as
# poses daquele personagem usam a mesma escala e a mesma linha dos pés
# medidas nesta pose, então trocar de pose nunca muda o tamanho nem faz
# o personagem "pular".
REFERENCE_POSE = {
    "menino": "menino/corpo_feliz",
    "mae":    "mae/corpo_neutro",
    "lipe":   "lipe/corpo_neutro",
    "amiga1": "amigos/amiga1_neutra",
    "amigo2": "amigos/amigo2_neutro",
    "amiga3": "amigos/amiga3_neutra",
}

_image_cache: dict = {}
_missing: set = set()           # arquivos que faltaram (avisados 1x cada)
_scaled_cache: dict = {}
_metrics_cache: dict = {}


def _placeholder(label: str, size: tuple) -> pygame.Surface:
    """Retângulo com X e o nome do arquivo, para imagem que não existe."""
    w, h = size
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill((*C_UI_DARK, 200))
    border = max(2, w // 120)
    pygame.draw.rect(surf, C_UI_LIGHT, surf.get_rect(), border)
    pygame.draw.line(surf, C_UI_LIGHT, (0, 0), (w, h), border)
    pygame.draw.line(surf, C_UI_LIGHT, (w, 0), (0, h), border)
    txt = font(max(14, w // 14), bold=True).render(label, True, C_UI_LIGHT, C_UI_DARK)
    surf.blit(txt, txt.get_rect(center=(w // 2, h // 2)))
    return surf


def get_image(rel_path: str, alpha: bool = True,
              placeholder_size: tuple = (1080, 1920)) -> pygame.Surface:
    """
    Carrega (com cache) uma imagem relativa à raiz do projeto.
    Se o arquivo não existir ou não abrir, devolve um placeholder com o
    nome do arquivo e avisa no console uma única vez — o jogo não quebra.
    """
    key = (rel_path, alpha)
    if key in _image_cache:
        return _image_cache[key]
    try:
        img = pygame.image.load(_path(rel_path))
        img = img.convert_alpha() if alpha else img.convert()
    except (FileNotFoundError, pygame.error) as e:
        if rel_path not in _missing:
            _missing.add(rel_path)
            print(f"[AVISO] Imagem não encontrada: {rel_path} ({e}) — usando placeholder.")
        img = _placeholder(os.path.basename(rel_path), placeholder_size)
    _image_cache[key] = img
    return img


def image_missing(rel_path: str) -> bool:
    return rel_path in _missing


# ── Fundos ────────────────────────────────────────────────────────────────────
def background_cover(name: str, size: tuple) -> pygame.Surface:
    """
    Fundo `assets/images/backgrounds/<name>.png` escalado em modo
    "cover": preenche todo o `size` mantendo a proporção e corta o
    excesso igualmente dos dois lados (16:9 em canvas 4:3 → corta as
    laterais). Resultado em cache por (nome, tamanho).
    """
    key = ("bg", name, size)
    if key in _scaled_cache:
        return _scaled_cache[key]
    src = get_image(os.path.join(IMAGES_DIR, "backgrounds", f"{name}.png"),
                    alpha=False, placeholder_size=(1920, 1080))
    sw, sh = src.get_size()
    tw, th = size
    scale = max(tw / sw, th / sh)
    scaled = pygame.transform.smoothscale(src, (max(1, round(sw * scale)),
                                                max(1, round(sh * scale))))
    out = pygame.Surface(size).convert()
    out.blit(scaled, ((tw - scaled.get_width()) // 2,
                      (th - scaled.get_height()) // 2))
    _scaled_cache[key] = out
    return out


# ── Personagens ───────────────────────────────────────────────────────────────
def _character_id(pose: str) -> str:
    """'menino/corpo_feliz' → 'menino'; 'amigos/amiga1_neutra' → 'amiga1'."""
    folder, _, fname = pose.partition("/")
    return fname.split("_")[0] if folder == "amigos" else folder


def _pose_raw(pose: str) -> pygame.Surface:
    """Imagem da pose no tamanho original, já em pé (girada se preciso)."""
    key = ("pose", pose)
    if key in _image_cache:
        return _image_cache[key]
    rel = os.path.join(IMAGES_DIR, "characters", f"{pose}.png")
    img = get_image(rel, alpha=True)
    if pose.startswith(ROTATED_PREFIXES) and not image_missing(rel):
        img = pygame.transform.rotate(img, -90)     # horário: cabeça para cima
    _image_cache[key] = img
    return img


def _character_metrics(char_id: str, fallback_pose: str) -> tuple:
    """(altura do corpo, linha dos pés, centro x) medidos na pose de referência."""
    if char_id in _metrics_cache:
        return _metrics_cache[char_id]
    ref = REFERENCE_POSE.get(char_id, fallback_pose)
    rel = os.path.join(IMAGES_DIR, "characters", f"{ref}.png")
    img = _pose_raw(ref)
    if image_missing(rel):              # sem referência: usa a própria pose
        img = _pose_raw(fallback_pose)
    r = img.get_bounding_rect(min_alpha=128)
    if r.height == 0:
        r = img.get_rect()
    metrics = (r.height, r.bottom, r.centerx)
    _metrics_cache[char_id] = metrics
    return metrics


def character_sprite(pose: str, body_height_px: int) -> tuple:
    """
    Devolve (surface, (ancora_x, ancora_y)) da pose, escalada para que o
    personagem (medido na pose de referência) tenha `body_height_px` de
    altura. A âncora é o ponto "entre os pés" dentro da surface: quem
    desenha posiciona esse ponto na linha do chão.
    """
    key = ("char", pose, body_height_px)
    if key in _scaled_cache:
        return _scaled_cache[key]
    raw = _pose_raw(pose)
    body_h, feet_y, center_x = _character_metrics(_character_id(pose), pose)
    s = body_height_px / body_h
    w, h = raw.get_size()
    surf = pygame.transform.smoothscale(raw, (max(1, round(w * s)), max(1, round(h * s))))
    result = (surf, (round(center_x * s), round(feet_y * s)))
    _scaled_cache[key] = result
    return result


def portrait(name: str, height_px: int) -> pygame.Surface:
    """Busto `characters/<name>.png` (ex.: 'lipe/rosto_alegre') recortado e escalado."""
    key = ("portrait", name, height_px)
    if key in _scaled_cache:
        return _scaled_cache[key]
    img = get_image(os.path.join(IMAGES_DIR, "characters", f"{name}.png"),
                    alpha=True, placeholder_size=(600, 600))
    r = img.get_bounding_rect(min_alpha=128)
    if r.height:
        img = img.subsurface(r)
    s = height_px / img.get_height()
    surf = pygame.transform.smoothscale(img, (max(1, round(img.get_width() * s)), height_px))
    _scaled_cache[key] = surf
    return surf