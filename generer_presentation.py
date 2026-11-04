"""Génère la présentation PowerPoint à partir des résultats de l'étape 7 du projet GTFS."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
NAVY = RGBColor(22, 48, 74)
TEAL = RGBColor(23, 107, 135)
ORANGE = RGBColor(217, 121, 65)
INK = RGBColor(42, 54, 66)
MUTED = RGBColor(98, 112, 124)
PALE = RGBColor(239, 245, 248)
WHITE = RGBColor(255, 255, 255)
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Rapport introuvable : {path}")
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Tableau introuvable : {path}")
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def format_number(value: int | float, decimals: int = 0) -> str:
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", " ").replace(".", ",")


def format_date(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value[6:8]}/{value[4:6]}/{value[:4]}"
    return value


def add_text(
    slide,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    size: int = 18,
    color: RGBColor = INK,
    bold: bool = False,
    align: PP_ALIGN = PP_ALIGN.LEFT,
) -> None:
    box = slide.shapes.add_textbox(
        Inches(x), Inches(y), Inches(width), Inches(height)
    )
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.04)
    frame.margin_right = Inches(0.04)
    frame.margin_top = Inches(0.02)
    frame.margin_bottom = Inches(0.02)
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.text = text
    paragraph.font.name = "Aptos"
    paragraph.font.size = Pt(size)
    paragraph.font.bold = bold
    paragraph.font.color.rgb = color


def add_bullets(
    slide,
    items: list[str],
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    size: int = 19,
    color: RGBColor = INK,
) -> None:
    box = slide.shapes.add_textbox(
        Inches(x), Inches(y), Inches(width), Inches(height)
    )
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.08)
    frame.margin_right = Inches(0.08)
    for index, item in enumerate(items):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = f"•  {item}"
        paragraph.level = 0
        paragraph.space_after = Pt(12)
        paragraph.font.name = "Aptos"
        paragraph.font.size = Pt(size)
        paragraph.font.color.rgb = color


def add_title(slide, title: str, subtitle: str | None = None) -> None:
    add_text(slide, title, 0.7, 0.35, 11.9, 0.55, size=27, color=NAVY, bold=True)
    if subtitle:
        add_text(slide, subtitle, 0.72, 0.98, 11.7, 0.42, size=13, color=MUTED)
    rule = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0.72), Inches(1.45), Inches(0.8), Inches(0.06)
    )
    rule.fill.solid()
    rule.fill.fore_color.rgb = TEAL
    rule.line.fill.background()


def add_footer(slide, slide_number: int) -> None:
    add_text(
        slide,
        "Analyse de l’offre de transport collectif • Pays de la Loire",
        0.72,
        7.12,
        10.7,
        0.2,
        size=9,
        color=MUTED,
    )
    add_text(slide, str(slide_number), 12.0, 7.08, 0.55, 0.25, size=10, color=MUTED, align=PP_ALIGN.RIGHT)


def new_content_slide(prs: Presentation, title: str, subtitle: str | None = None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, title, subtitle)
    add_footer(slide, len(prs.slides))
    return slide


def add_metric_card(slide, x: float, y: float, value: str, label: str, accent=TEAL) -> None:
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(x),
        Inches(y),
        Inches(2.7),
        Inches(1.25),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = PALE
    shape.line.fill.background()
    add_text(slide, value, x + 0.15, y + 0.16, 2.4, 0.45, size=25, color=accent, bold=True, align=PP_ALIGN.CENTER)
    add_text(slide, label, x + 0.15, y + 0.68, 2.4, 0.38, size=12, color=MUTED, align=PP_ALIGN.CENTER)


def add_picture(slide, filename: str, x: float, y: float, width: float, height: float) -> None:
    path = REPORTS / filename
    if not path.is_file():
        raise FileNotFoundError(f"Graphique introuvable : {path}")
    slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(width), height=Inches(height))


def add_table(slide, headers: list[str], rows: list[list[str]], x: float, y: float, width: float, height: float,
              col_widths: list[float] | None = None) -> None:
    table = slide.shapes.add_table(
        len(rows) + 1,
        len(headers),
        Inches(x),
        Inches(y),
        Inches(width),
        Inches(height),
    ).table
    table.first_row = True
    if col_widths:
        for column, col_width in enumerate(col_widths):
            table.columns[column].width = Inches(col_width)
    for column, header in enumerate(headers):
        cell = table.cell(0, column)
        cell.text = header
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        for paragraph in cell.text_frame.paragraphs:
            paragraph.font.bold = True
            paragraph.font.size = Pt(12)
            paragraph.font.color.rgb = WHITE
    for row_index, row in enumerate(rows, start=1):
        for column, value in enumerate(row):
            cell = table.cell(row_index, column)
            cell.text = value
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if row_index % 2 else PALE
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.name = "Aptos"
                paragraph.font.size = Pt(11)
                paragraph.font.color.rgb = INK


def format_iso(value: str) -> str:
    """2025-04-07 -> 07/04/2025."""
    return format_date(value.replace("-", ""))


def pct(value: float, decimals: int = 0) -> str:
    return f"{format_number(value * 100, decimals)} %"


def build_presentation(output: Path) -> None:
    """Présentation fondée sur l'étape 7 (fenêtre de service valide, grille complète, prévision revue)."""
    e7 = read_json(REPORTS / "etape7_offre_fenetre_valide.json")
    perimetre, horizon, profil = e7["perimetre"], e7["horizon_feed"], e7["profil_offre"]
    prevision, desserte = e7["prevision"], e7["faible_desserte"]
    debut, fin = prevision["fenetre"]
    modeles = prevision["modeles"]
    retenu = modeles[prevision["modele_retenu"]]
    v1 = modeles["baseline_v1_arret_periode"]

    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    # 1. Titre
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.background.fill
    background.solid()
    background.fore_color.rgb = NAVY
    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.18), SLIDE_HEIGHT)
    accent.fill.solid()
    accent.fill.fore_color.rgb = TEAL
    accent.line.fill.background()
    add_text(slide, "MOBILITÉ • PAYS DE LA LOIRE", 0.85, 0.85, 10.7, 0.45, size=15, color=RGBColor(153, 214, 222), bold=True)
    add_text(slide, "Analyser l’offre\npour éclairer la desserte", 0.85, 1.65, 11.4, 1.8, size=36, color=WHITE, bold=True)
    add_text(slide, "Analyse de l’offre planifiée et prévision à partir des données GTFS DESTINEO",
             0.9, 4.0, 10.9, 0.8, size=20, color=WHITE)
    add_text(slide, f"Période étudiée : {format_iso(debut)} – {format_iso(fin)} (12 semaines de service complet)",
             0.9, 6.55, 10.5, 0.35, size=13, color=RGBColor(203, 216, 226))

    # 2. Question et périmètre
    slide = new_content_slide(prs, "Question métier et périmètre")
    add_text(slide, "Comment repérer les arrêts et créneaux où l’offre théorique est la plus faible, puis estimer le niveau d’offre attendu ?",
             0.85, 1.85, 7.0, 1.2, size=23, color=NAVY, bold=True)
    add_bullets(slide, [
        "Indicateur : départs planifiés par arrêt, date et période horaire ; un départ est un passage où la montée est possible.",
        "Périmètre : arrêts situés dans les Pays de la Loire, sur les 12 semaines où le feed décrit tout le service.",
        "Grille complète : les créneaux sans aucun départ comptent pour 0, ce qui fait apparaître les arrêts mal desservis.",
        "Offre planifiée uniquement : ni fréquentation, ni demande, ni retards.",
    ], 0.9, 3.25, 7.0, 3.3, size=16)
    add_metric_card(slide, 9.0, 1.85, f"{format_number(perimetre['grille_observations'] / 1e6, 1)} M", "observations arrêt-date-période")
    add_metric_card(slide, 9.0, 3.3, format_number(desserte["arrets_regionaux_actifs"]), "arrêts régionaux actifs", accent=ORANGE)
    add_metric_card(slide, 9.0, 4.75, pct(perimetre["part_creneaux_sans_depart"]), "des créneaux sans aucun départ")

    # 3. Socle de données
    slide = new_content_slide(prs, "Un socle de données contrôlé")
    add_text(slide, "Chaîne de traitement", 0.9, 1.8, 5.7, 0.4, size=20, color=NAVY, bold=True)
    add_bullets(slide, [
        "Fichiers GTFS : lignes, trajets, arrêts et horaires.",
        "Contrôle et nettoyage, puis base SQLite normalisée et API FastAPI testée.",
        f"{format_number(perimetre['passages_sans_montee_exclus'])} passages sans montée possible (souvent des terminus) exclus des départs.",
        "Analyse et prévision sur une grille complète arrêt × date × période.",
    ], 0.9, 2.35, 6.3, 3.4, size=16)
    add_text(slide, "Base de référence", 7.45, 1.8, 4.4, 0.4, size=20, color=NAVY, bold=True)
    add_metric_card(slide, 7.45, 2.4, f"{format_number(perimetre['passages_total'] / 1e6, 1)} M", "passages horaires contrôlés")
    add_metric_card(slide, 10.35, 2.4, "20 170", "arrêts")
    add_metric_card(slide, 7.45, 4.0, "182 725", "trajets planifiés", accent=ORANGE)
    add_metric_card(slide, 10.35, 4.0, "1 029", "lignes")
    add_text(slide, f"Calendrier du feed : {format_iso(horizon['date_min_calendar'])} au {format_iso(horizon['date_max_calendar'])}, "
                    f"mais service complet seulement jusqu’au {format_iso(horizon['derniere_date_offre_complete'])}.",
             7.5, 5.6, 5.5, 0.8, size=13, color=MUTED)

    # 4. Audit
    slide = new_content_slide(prs, "Ce que l’audit méthodologique a corrigé")
    add_picture(slide, "etape7_horizon_feed.png", 0.75, 1.7, 11.8, 3.78)
    add_bullets(slide, [
        f"Après juin 2025, le feed ne décrit presque plus rien ({format_number(horizon['departs_jour_median_2026'])} départs par jour en 2026) : "
        "l’ancien test (588 observations, toutes égales à 1) ne mesurait rien. Analyse limitée à la fenêtre verte.",
        f"{format_number(perimetre['dont_sncf'])} gares SNCF hors région retirées du périmètre ; créneaux à 0 réintégrés.",
    ], 0.8, 5.55, 11.8, 1.5, size=14)

    # 5. Profil horaire
    slide = new_content_slide(prs, "L’offre varie selon l’heure et le type de jour")
    add_picture(slide, "etape7_profil_horaire.png", 0.75, 1.7, 8.2, 3.12)
    par_heure = profil["departs_par_heure_ouvre"]
    jour = profil["departs_regionaux_par_jour"]
    add_metric_card(slide, 9.6, 1.75, format_number(jour["ouvre"]), "départs par jour ouvré")
    add_metric_card(slide, 9.6, 3.2, f"−{pct(profil['baisse_samedi_vs_ouvre'])}", "le samedi", accent=ORANGE)
    add_metric_card(slide, 9.6, 4.65, f"−{pct(profil['baisse_dimanche_vs_ouvre'])}", "le dimanche et les jours fériés", accent=ORANGE)
    add_text(slide, f"Deux pointes en semaine : {format_number(par_heure['morning_peak'])} départs par heure de 6 h à 9 h et "
                    f"{format_number(par_heure['evening_peak'])} de 17 h à 20 h, contre {format_number(par_heure['night_service'])} après 20 h.",
             0.85, 5.15, 8.3, 0.75, size=15, color=INK)
    add_text(slide, "Le samedi, l’offre de la pointe du matin est divisée par deux ; le dimanche, le service est réduit sur toute la journée.",
             0.85, 6.0, 8.3, 0.75, size=15, color=TEAL, bold=True)

    # 6. Faible desserte
    slide = new_content_slide(prs, "Où l’offre est la plus faible")
    add_picture(slide, "etape7_carte_offre.png", 0.7, 1.65, 5.1, 4.73)
    add_metric_card(slide, 6.2, 1.8, pct(desserte["part_arrets_moins_de_5_departs_jour"]), "des arrêts sous 5 départs par jour ouvré", accent=ORANGE)
    add_metric_card(slide, 9.2, 1.8, pct(desserte["part_arrets_sans_depart_pointe_matin"]), "sans aucun départ entre 6 h et 9 h", accent=ORANGE)
    reseaux = {r["reseau"]: r for r in desserte["par_reseau"]}
    lignes = []
    for code, nom in [("ALEOP", "ALEOP (interurbain)"), ("TAN", "TAN (Nantes)"), ("CHOLETBUS", "Choletbus"), ("SNCF", "SNCF (gares régionales)")]:
        r = reseaux[code]
        lignes.append([nom, format_number(r["arrets"]), format_number(r["departs_jour_median"], 0),
                       pct(r["part_moins_de_5_departs"]), pct(r["part_sans_pointe_matin"])])
    add_table(slide, ["Réseau", "Arrêts", "Départs / jour\n(médiane)", "< 5 départs", "Sans pointe\nmatin"], lignes, 6.2, 3.35, 6.3, 2.3,
              col_widths=[2.0, 0.9, 1.2, 1.0, 1.2])
    add_text(slide, f"La faible desserte est d’abord interurbaine : la moitié des arrêts ALEOP ont {format_number(reseaux['ALEOP']['departs_jour_median'])} départs par jour ou moins. "
                    f"Médiane régionale : {format_number(desserte['departs_jour_median'], 1)}.",
             6.2, 5.85, 6.3, 0.95, size=14, color=TEAL, bold=True)

    # 7. Prévision : comparaison
    slide = new_content_slide(prs, "Prévoir : bien modéliser le calendrier suffit")
    noms = [("baseline_v1_arret_periode", "Baseline V1 : moyenne arrêt × période"),
            ("baseline_calendrier", "Calendrier : arrêt × type de jour × période"),
            ("baseline_calendrier_recent", "Calendrier récent (2 dernières semaines)"),
            ("baseline_calendrier_recent_ponts", "Calendrier récent + ajustement des ponts"),
            ("hist_gradient_boosting", "Gradient boosting (perte de Poisson)")]
    rows = [[label + ("  ✔" if key == prevision["modele_retenu"] else ""), format_number(modeles[key]["mae"], 3),
             format_number(modeles[key]["rmse"], 3), format_number(modeles[key]["mae_feries_ponts"], 3),
             format_number(modeles[key]["mae_jours_normaux"], 3)] for key, label in noms]
    add_table(slide, ["Méthode", "MAE", "RMSE", "MAE fériés\net ponts", "MAE jours\nnormaux"], rows, 0.9, 1.85, 11.5, 2.9,
              col_widths=[5.1, 1.5, 1.5, 1.7, 1.7])
    add_text(slide, f"Méthode retenue : calendrier récent + ponts, MAE {format_number(retenu['mae'], 3)} départ, "
                    f"soit une erreur divisée par {format_number(v1['mae'] / retenu['mae'])} par rapport à la baseline V1.",
             1.0, 5.0, 11.1, 0.55, size=17, color=TEAL, bold=True)
    add_text(slide, f"Entraînement du {format_iso(prevision['entrainement'][0])} au {format_iso(prevision['entrainement'][1])}, "
                    f"test du {format_iso(prevision['test'][0])} au {format_iso(prevision['test'][1])} : "
                    f"{format_number(prevision['observations_test'])} observations, dont l’Ascension, son pont et le lundi de Pentecôte. "
                    "La MAE est l’écart moyen, en départs, par arrêt et période.",
             1.0, 5.65, 11.1, 0.9, size=14, color=INK)

    # 8. Prévision vs réel
    slide = new_content_slide(prs, "La prévision suit l’offre réelle jour après jour")
    add_picture(slide, "etape7_prevision_vs_reel.png", 0.75, 1.7, 11.8, 4.13)
    add_text(slide, "Le gradient boosting fait moins bien (MAE "
                    f"{format_number(modeles['hist_gradient_boosting']['mae'], 3)}) : il apprend sur des semaines antérieures au changement d’offre de la TAN "
                    "à la mi-mai. Pour une offre planifiée, ce qui compte est de représenter le calendrier et de repérer les ruptures d’offre.",
             0.85, 5.95, 11.7, 0.95, size=15, color=INK)

    # 9. Limites
    slide = new_content_slide(prs, "Limites et pistes pour la décision")
    add_bullets(slide, [
        "Offre planifiée sur 3 mois du printemps 2025 : ni fréquentation, ni retards, ni suppressions de service.",
        "Réseaux urbains d’Angers, Laval, Saint-Nazaire et La Roche-sur-Yon absents de l’export (agences sans lignes).",
        "Le comptage par arrêt dépend du découpage des arrêts physiques (quais), propre à chaque réseau.",
        "Recalibrer la prévision à chaque nouveau feed et surveiller les ruptures d’offre (exemple : TAN mi-mai).",
        "Un indicateur de faible offre ne mesure pas le besoin : croiser avec la population desservie avant d’arbitrer.",
    ], 0.9, 1.85, 11.5, 3.9, size=16)
    add_text(slide, "À retenir : prioriser l’analyse des arrêts interurbains sans départ en pointe du matin, puis compléter par la "
                    "fréquentation réelle, la demande locale et une validation métier avant tout arbitrage de desserte.",
             0.95, 5.85, 11.3, 0.85, size=17, color=TEAL, bold=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    prs.save(output)
    print(f"Présentation créée : {output}")
    print(f"Nombre de diapositives : {len(prs.slides)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Génère une présentation PowerPoint à partir des rapports GTFS."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPORTS / "presentation_analyse_mobilite.pptx",
        help="Chemin du PowerPoint à créer (défaut : reports/presentation_analyse_mobilite.pptx).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    build_presentation(output)


if __name__ == "__main__":
    main()
