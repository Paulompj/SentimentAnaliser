"""
Gera um PowerPoint com exemplos visuais para cada etapa do pipeline
de PLN e Análise de Sentimentos — Visual acadêmico/sóbrio para TCC.

Exemplo usado: "O candidato é muito bom!!! 🇧🇷🔥 kkkk"
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pathlib import Path

# ── Paleta acadêmica ─────────────────────────────────────────────────────
WHITE       = RGBColor(255, 255, 255)
BLACK       = RGBColor(0, 0, 0)
DARK_GRAY   = RGBColor(50, 50, 50)
MID_GRAY    = RGBColor(120, 120, 120)
LIGHT_GRAY  = RGBColor(230, 230, 230)
LIGHTER_GRAY= RGBColor(245, 245, 245)
BORDER_GRAY = RGBColor(180, 180, 180)
HEADER_BLUE = RGBColor(40, 60, 90)
HEADER_BG   = RGBColor(40, 60, 90)
SUBHEADER   = RGBColor(60, 80, 110)
STRIKETHROUGH_RED = RGBColor(180, 50, 50)

SLIDE_WIDTH  = Inches(13.33)
SLIDE_HEIGHT = Inches(7.5)


def set_slide_bg(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_box(slide, left, top, width, height, fill_color, text="",
            font_size=14, font_color=BLACK, bold=False,
            alignment=PP_ALIGN.CENTER, border_color=BORDER_GRAY,
            border_width=Pt(0.75), shape_type=MSO_SHAPE.RECTANGLE):
    shape = slide.shapes.add_shape(shape_type, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color

    if border_color:
        shape.line.color.rgb = border_color
        shape.line.width = border_width
    else:
        shape.line.fill.background()

    tf = shape.text_frame
    tf.word_wrap = True
    tf.auto_size = None

    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.font.size = Pt(font_size)
        p.font.color.rgb = font_color
        p.font.bold = bold
        p.alignment = alignment
    return shape


def add_arrow_down(slide, left, top, width, height):
    shape = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = MID_GRAY
    shape.line.fill.background()
    return shape


def add_arrow_right(slide, left, top, width, height):
    shape = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = MID_GRAY
    shape.line.fill.background()
    return shape


def add_title(slide, text, subtitle=""):
    add_box(slide, Inches(0.5), Inches(0.3), Inches(12.33), Inches(0.7),
            HEADER_BG, text, font_size=22, font_color=WHITE, bold=True,
            border_color=HEADER_BG)
    if subtitle:
        add_box(slide, Inches(0.5), Inches(1.05), Inches(12.33), Inches(0.45),
                WHITE, subtitle, font_size=12, font_color=MID_GRAY,
                border_color=None)


def add_label(slide, left, top, text, color=HEADER_BLUE):
    add_box(slide, left, top, Inches(1.3), Inches(0.35),
            color, text, font_size=11, bold=True, font_color=WHITE,
            border_color=color)


def add_table_row(slide, x_start, y, col_widths, values, bg_color,
                  font_color=DARK_GRAY, font_size=12, bold=False):
    x = x_start
    for val, w in zip(values, col_widths):
        add_box(slide, x, y, w, Inches(0.38),
                bg_color, val, font_size=font_size, font_color=font_color,
                bold=bold, border_color=BORDER_GRAY if not bold else bg_color)
        x += w + Inches(0.05)


# ══════════════════════════════════════════════════════════════════════════
# SLIDE 1 — Pré-processamento
# ══════════════════════════════════════════════════════════════════════════
def slide_preprocessamento(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_title(slide,
              "Etapa 1 — Pré-processamento",
              "Remoção de pontuações, emojis e caracteres especiais por meio de expressões regulares.")

    add_label(slide, Inches(0.8), Inches(2.0), "Entrada")
    add_box(slide, Inches(0.8), Inches(2.5), Inches(11.7), Inches(0.8),
            LIGHTER_GRAY,
            '"O candidato é muito bom!!! \U0001f1e7\U0001f1f7\U0001f525 kkkk"',
            font_size=20, font_color=DARK_GRAY)

    add_arrow_down(slide, Inches(6.2), Inches(3.5), Inches(0.7), Inches(0.5))
    add_box(slide, Inches(3.8), Inches(3.5), Inches(2.2), Inches(0.4),
            WHITE, 'regex: [^\\w\\s]|_', font_size=11, font_color=MID_GRAY,
            border_color=None)

    add_box(slide, Inches(7.5), Inches(3.45), Inches(5.0), Inches(0.55),
            LIGHTER_GRAY,
            'Elementos removidos:   !!!     \U0001f1e7\U0001f1f7     \U0001f525',
            font_size=13, font_color=STRIKETHROUGH_RED)

    add_label(slide, Inches(0.8), Inches(4.3), "Saída")
    add_box(slide, Inches(0.8), Inches(4.8), Inches(11.7), Inches(0.8),
            LIGHTER_GRAY,
            '"O candidato é muito bom kkkk"',
            font_size=20, font_color=DARK_GRAY,
            border_color=HEADER_BLUE, border_width=Pt(1.5))


# ══════════════════════════════════════════════════════════════════════════
# SLIDE 2 — Classificação Gramatical e Lematização
# ══════════════════════════════════════════════════════════════════════════
def slide_pos_lemma(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_title(slide,
              "Etapa 2 — Classificação Gramatical e Lematização",
              "Aplicação do modelo pt_core_news_lg do spaCy para tokenização, POS tagging e lematização.")

    add_label(slide, Inches(0.8), Inches(1.8), "Entrada")
    add_box(slide, Inches(0.8), Inches(2.2), Inches(11.7), Inches(0.65),
            LIGHTER_GRAY, '"o candidato é muito bom kkkk"',
            font_size=18, font_color=DARK_GRAY)

    add_arrow_down(slide, Inches(6.2), Inches(3.0), Inches(0.7), Inches(0.4))

    palavras = [
        ("o",          "o",          "DET",   "Determinante"),
        ("candidato",  "candidato",  "NOUN",  "Substantivo"),
        ("é",          "ser",        "VERB",  "Verbo"),
        ("muito",      "muito",      "ADV",   "Advérbio"),
        ("bom",        "bom",        "ADJ",   "Adjetivo"),
        ("kkkk",       "kkkk",       "INTJ",  "Interjeição"),
    ]

    headers = ["Palavra", "Lema", "POS Tag", "Descrição"]
    col_widths = [Inches(2.5), Inches(2.5), Inches(2.0), Inches(4.6)]
    x_start = Inches(0.8)

    add_table_row(slide, x_start, Inches(3.6), col_widths, headers,
                  HEADER_BG, font_color=WHITE, font_size=12, bold=True)

    for row_i, (pal, lema, pos, desc) in enumerate(palavras):
        y = Inches(4.03) + row_i * Inches(0.40)
        bg = LIGHTER_GRAY if row_i % 2 == 0 else WHITE
        add_table_row(slide, x_start, y, col_widths, [pal, lema, pos, desc], bg)

    add_box(slide, Inches(0.8), Inches(6.5), Inches(11.7), Inches(0.5),
            WHITE,
            'Destaque: o verbo flexionado "é" foi lematizado para sua forma infinitiva "ser".',
            font_size=12, font_color=MID_GRAY, alignment=PP_ALIGN.LEFT,
            border_color=None)


# ══════════════════════════════════════════════════════════════════════════
# SLIDE 3 — Tabela de Referência POS Tags
# ══════════════════════════════════════════════════════════════════════════
def slide_pos_tags_referencia(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_title(slide,
              "Referência — Classes Gramaticais (POS Tags)",
              "Tags utilizadas pelo modelo spaCy (Universal Dependencies) para classificação gramatical das palavras.")

    tags = [
        ("ADJ",   "Adjetivo",        "Palavra que qualifica ou caracteriza um substantivo.",
         "bom, grande, feliz"),
        ("ADV",   "Advérbio",        "Palavra que modifica um verbo, adjetivo ou outro advérbio.",
         "muito, bem, sempre"),
        ("DET",   "Determinante",    "Palavra que acompanha o substantivo, determinando-o.",
         "o, a, um, os, esta"),
        ("INTJ",  "Interjeição",     "Palavra ou expressão que exprime emoção ou reação.",
         "kkkk, ah, nossa"),
        ("NOUN",  "Substantivo",     "Palavra que designa seres, objetos, lugares ou conceitos.",
         "candidato, debate, país"),
        ("PROPN", "Nome Próprio",    "Substantivo que designa um ser ou entidade específica.",
         "Brasil, YouTube, Paulo"),
        ("VERB",  "Verbo",           "Palavra que expressa ação, estado ou fenômeno.",
         "ser, falar, votar"),
        ("ADP",   "Preposição",      "Palavra que estabelece relação entre termos da oração.",
         "de, em, para, com"),
        ("CONJ",  "Conjunção",       "Palavra que liga orações ou termos de mesma função.",
         "e, mas, ou, porque"),
        ("PRON",  "Pronome",         "Palavra que substitui ou acompanha o substantivo.",
         "ele, ela, isso, que"),
        ("NUM",   "Numeral",         "Palavra que indica quantidade ou ordem.",
         "um, dois, primeiro"),
        ("PUNCT", "Pontuação",       "Sinais gráficos de pontuação.",
         ". , ! ? ;"),
    ]

    headers = ["Tag", "Classe Gramatical", "Descrição", "Exemplos"]
    col_widths = [Inches(1.2), Inches(2.5), Inches(5.5), Inches(3.0)]
    x_start = Inches(0.5)

    add_table_row(slide, x_start, Inches(1.8), col_widths, headers,
                  HEADER_BG, font_color=WHITE, font_size=12, bold=True)

    for row_i, (tag, classe, desc, exemplos) in enumerate(tags):
        y = Inches(2.23) + row_i * Inches(0.40)
        bg = LIGHTER_GRAY if row_i % 2 == 0 else WHITE
        vals = [tag, classe, desc, exemplos]

        x = x_start
        for col_i, (val, w) in enumerate(zip(vals, col_widths)):
            fc = DARK_GRAY
            al = PP_ALIGN.LEFT if col_i >= 2 else PP_ALIGN.CENTER
            bd = True if col_i == 0 else False
            add_box(slide, x, y, w, Inches(0.38),
                    bg, val, font_size=10, font_color=fc,
                    bold=bd, alignment=al)
            x += w + Inches(0.05)

    # Nota de rodapé
    add_box(slide, Inches(0.5), Inches(7.05), Inches(12.3), Inches(0.35),
            WHITE,
            'Fonte: Universal Dependencies (UD) — padrão utilizado pelo spaCy para anotação morfossintática.',
            font_size=10, font_color=MID_GRAY, alignment=PP_ALIGN.LEFT,
            border_color=None)


# ══════════════════════════════════════════════════════════════════════════
# SLIDE 4 — Remoção de Stopwords
# ══════════════════════════════════════════════════════════════════════════
def slide_stopwords(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_title(slide,
              "Etapa 3 — Remoção de Stopwords",
              "Exclusão de palavras sem carga semântica relevante (artigos, preposições, conjunções) — NLTK.")

    add_label(slide, Inches(0.8), Inches(2.0), "Entrada")

    tokens_before = [
        ("o", True), ("candidato", False), ("ser", True),
        ("muito", False), ("bom", False), ("kkkk", False)
    ]

    x = Inches(0.8)
    for token, is_stop in tokens_before:
        w = Inches(len(token) * 0.20 + 0.7)
        bg = RGBColor(250, 235, 235) if is_stop else LIGHTER_GRAY
        border = STRIKETHROUGH_RED if is_stop else BORDER_GRAY
        fc = STRIKETHROUGH_RED if is_stop else DARK_GRAY
        add_box(slide, x, Inches(2.5), w, Inches(0.55),
                bg, token, font_size=15, font_color=fc, bold=is_stop,
                border_color=border, border_width=Pt(1.5) if is_stop else Pt(0.75))
        x += w + Inches(0.15)

    add_box(slide, Inches(9.0), Inches(2.5), Inches(3.5), Inches(0.55),
            WHITE, 'Borda vermelha = stopword',
            font_size=11, font_color=STRIKETHROUGH_RED,
            border_color=None)

    add_arrow_down(slide, Inches(5.5), Inches(3.3), Inches(0.7), Inches(0.5))

    add_label(slide, Inches(0.8), Inches(4.1), "Saída")

    tokens_after = ["candidato", "muito", "bom", "kkkk"]
    x = Inches(0.8)
    for token in tokens_after:
        w = Inches(len(token) * 0.20 + 0.7)
        add_box(slide, x, Inches(4.6), w, Inches(0.55),
                LIGHTER_GRAY, token, font_size=15, font_color=DARK_GRAY,
                border_color=HEADER_BLUE, border_width=Pt(1.5))
        x += w + Inches(0.15)

    add_box(slide, Inches(0.8), Inches(5.6), Inches(11.7), Inches(0.8),
            LIGHTER_GRAY,
            'Stopwords removidas: "o" (determinante) e "ser" (verbo auxiliar/de ligação).\n'
            'Essas palavras não contribuem para a polaridade de sentimento do comentário.',
            font_size=12, font_color=MID_GRAY, alignment=PP_ALIGN.LEFT)


# ══════════════════════════════════════════════════════════════════════════
# SLIDE 5 — Cálculo de Polaridade
# ══════════════════════════════════════════════════════════════════════════
def slide_polaridade(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_title(slide,
              "Etapa 4 — Cálculo de Polaridade",
              "Mapeamento: Lema (PT) → Open Multilingual WordNet → Synset → SentiWordNet (scores).")

    steps = [
        'Lema (PT)\n"bom"',
        'OMW\n(lang=por)',
        'Synset\ngood.a.01',
        'SentiWordNet\n(scores)',
    ]

    box_w = Inches(2.5)
    gap = Inches(0.4)
    arrow_w = Inches(0.6)
    start_x = Inches(0.5)

    for i, txt in enumerate(steps):
        x = start_x + i * (box_w + gap + arrow_w)
        add_box(slide, x, Inches(2.1), box_w, Inches(0.8),
                LIGHTER_GRAY, txt, font_size=13, font_color=DARK_GRAY, bold=True)
        if i < len(steps) - 1:
            ax = x + box_w + Inches(0.05)
            add_arrow_right(slide, ax, Inches(2.3), arrow_w - Inches(0.1), Inches(0.35))

    add_box(slide, Inches(0.5), Inches(3.4), Inches(12.3), Inches(0.4),
            HEADER_BG,
            'Synsets encontrados para "bom" (classe gramatical: ADJ)',
            font_size=13, bold=True, font_color=WHITE,
            border_color=HEADER_BG)

    headers = ["Synset", "pos_score", "neg_score", "obj_score"]
    col_widths = [Inches(4.0), Inches(2.5), Inches(2.5), Inches(2.5)]
    x_start = Inches(0.5)

    add_table_row(slide, x_start, Inches(3.85), col_widths, headers,
                  SUBHEADER, font_color=WHITE, font_size=11, bold=True)

    synset_data = [
        ("good.a.01",     "0.750", "0.000", "0.250"),
        ("good.a.03",     "0.250", "0.000", "0.750"),
        ("estimable.a.02","0.500", "0.000", "0.500"),
    ]

    for row_i, row in enumerate(synset_data):
        y = Inches(4.28) + row_i * Inches(0.38)
        bg = LIGHTER_GRAY if row_i % 2 == 0 else WHITE
        add_table_row(slide, x_start, y, col_widths, list(row), bg, font_size=11)

    add_box(slide, Inches(0.5), Inches(5.6), Inches(5.8), Inches(0.9),
            LIGHTER_GRAY,
            'Acumulado para "bom":\n  pos_total += 1.500    neg_total += 0.000',
            font_size=14, font_color=DARK_GRAY, alignment=PP_ALIGN.LEFT,
            border_color=HEADER_BLUE, border_width=Pt(1.5))

    add_box(slide, Inches(6.6), Inches(5.6), Inches(6.2), Inches(0.9),
            LIGHTER_GRAY,
            'O processo se repete para cada palavra restante.\n'
            'Palavras sem synset encontrado são ignoradas.',
            font_size=12, font_color=MID_GRAY, alignment=PP_ALIGN.LEFT)


# ══════════════════════════════════════════════════════════════════════════
# SLIDE 6 — Classificação do Comentário
# ══════════════════════════════════════════════════════════════════════════
def slide_classificacao(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_title(slide,
              "Etapa 5 — Classificação do Comentário",
              "Comparação entre a soma dos escores positivos e negativos para classificação final.")

    add_box(slide, Inches(1.0), Inches(2.3), Inches(5.0), Inches(0.9),
            LIGHTER_GRAY, 'pos_total = 1.875',
            font_size=26, bold=True, font_color=DARK_GRAY,
            border_color=HEADER_BLUE, border_width=Pt(1.5))

    add_box(slide, Inches(7.0), Inches(2.3), Inches(5.0), Inches(0.9),
            LIGHTER_GRAY, 'neg_total = 0.125',
            font_size=26, bold=True, font_color=DARK_GRAY,
            border_color=BORDER_GRAY, border_width=Pt(1.5))

    add_arrow_down(slide, Inches(3.2), Inches(3.4), Inches(0.6), Inches(0.5))
    add_arrow_down(slide, Inches(9.2), Inches(3.4), Inches(0.6), Inches(0.5))

    add_box(slide, Inches(2.5), Inches(4.1), Inches(8.3), Inches(0.7),
            LIGHTER_GRAY, 'pos_total (1.875)  >  neg_total (0.125)',
            font_size=20, bold=True, font_color=DARK_GRAY,
            border_color=HEADER_BLUE, border_width=Pt(1.5))

    add_arrow_down(slide, Inches(6.2), Inches(5.0), Inches(0.7), Inches(0.5))

    add_box(slide, Inches(3.5), Inches(5.7), Inches(6.3), Inches(0.8),
            HEADER_BG, 'Classificação: POSITIVO',
            font_size=26, bold=True, font_color=WHITE,
            border_color=HEADER_BG, border_width=Pt(2))

    add_box(slide, Inches(0.5), Inches(5.7), Inches(2.8), Inches(1.0),
            LIGHTER_GRAY,
            'Regras de classificação:\npos > neg → Positivo\nneg > pos → Negativo\npos = neg → Neutro',
            font_size=11, font_color=MID_GRAY, alignment=PP_ALIGN.LEFT)


# ══════════════════════════════════════════════════════════════════════════
# SLIDE 7 — Detecção de Candidato
# ══════════════════════════════════════════════════════════════════════════
def slide_candidato(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_title(slide,
              "Etapa 6 — Detecção de Candidato",
              "Identificação de menções a presidenciáveis por meio de dicionário de palavras-chave.")

    add_label(slide, Inches(0.8), Inches(1.9), "Comentário")
    add_box(slide, Inches(0.8), Inches(2.35), Inches(11.7), Inches(0.6),
            LIGHTER_GRAY,
            '"O candidato X é muito bom kkkk"',
            font_size=18, font_color=DARK_GRAY)

    add_arrow_down(slide, Inches(6.2), Inches(3.1), Inches(0.7), Inches(0.4))

    add_box(slide, Inches(0.8), Inches(3.7), Inches(5.5), Inches(0.4),
            HEADER_BG, 'Dicionário de palavras-chave',
            font_size=12, bold=True, font_color=WHITE,
            border_color=HEADER_BG)

    add_box(slide, Inches(0.8), Inches(4.15), Inches(5.5), Inches(0.85),
            LIGHTER_GRAY,
            'Candidato A:\n  "nome_candidato_a", "apelido_1", "apelido_2",\n  "numero_partido"',
            font_size=12, font_color=DARK_GRAY, alignment=PP_ALIGN.LEFT)

    add_box(slide, Inches(0.8), Inches(5.1), Inches(5.5), Inches(0.85),
            LIGHTER_GRAY,
            'Candidato B:\n  "nome_candidato_b", "apelido_1", "apelido_2",\n  "numero_partido"',
            font_size=12, font_color=DARK_GRAY, alignment=PP_ALIGN.LEFT)

    add_arrow_right(slide, Inches(6.5), Inches(4.4), Inches(0.7), Inches(0.4))

    add_box(slide, Inches(7.5), Inches(3.7), Inches(5.0), Inches(0.4),
            HEADER_BG, 'Resultado da detecção',
            font_size=12, bold=True, font_color=WHITE,
            border_color=HEADER_BG)

    add_box(slide, Inches(7.5), Inches(4.15), Inches(5.0), Inches(1.1),
            LIGHTER_GRAY,
            'Palavra encontrada: "candidato X"\n\n'
            'Candidato detectado: Candidato A\n'
            'Sentimento associado: Positivo',
            font_size=13, font_color=DARK_GRAY, alignment=PP_ALIGN.LEFT,
            border_color=HEADER_BLUE, border_width=Pt(1.5))

    add_box(slide, Inches(7.5), Inches(5.4), Inches(5.0), Inches(0.6),
            LIGHTER_GRAY,
            'Nenhuma palavra-chave do "Candidato B" encontrada.',
            font_size=12, font_color=MID_GRAY, alignment=PP_ALIGN.LEFT)

    # Nota
    add_box(slide, Inches(0.8), Inches(6.3), Inches(11.7), Inches(0.7),
            LIGHTER_GRAY,
            'O dicionário de palavras-chave é configurável e pode incluir nomes, apelidos,\n'
            'números de partido e variações comuns utilizadas pelo público.',
            font_size=11, font_color=MID_GRAY, alignment=PP_ALIGN.LEFT)


# ══════════════════════════════════════════════════════════════════════════
def main():
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    slide_preprocessamento(prs)
    slide_pos_lemma(prs)
    slide_pos_tags_referencia(prs)  # NOVO: tabela de referência POS tags
    slide_stopwords(prs)
    slide_polaridade(prs)
    slide_classificacao(prs)
    slide_candidato(prs)

    output_dir = Path(__file__).resolve().parents[1] / "docs" / "apresentacoes"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "pipeline_exemplos_v3.pptx"
    prs.save(output_path)
    print(f"PowerPoint gerado: {output_path}")
    print(f"Total de slides: {len(prs.slides)}")


if __name__ == "__main__":
    main()
