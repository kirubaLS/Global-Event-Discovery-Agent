"""
backend/geo_data.py — full world geography for the search geo backstop.

COUNTRIES maps every country (lowercase) to its region. REGIONS is built
dynamically from it (plus composite regions like APAC/EMEA/LATAM), so a
user can type ANY country or region name and _geo_ok can enforce it.
ALIASES maps common alternate spellings/abbreviations both ways.
"""

# country → region (regions: europe, asia, middle east, africa,
# north america, central america & caribbean, south america, oceania)
COUNTRIES = {
    # ── Europe ──────────────────────────────────────────────────────
    "albania": "europe", "andorra": "europe", "austria": "europe",
    "belarus": "europe", "belgium": "europe",
    "bosnia and herzegovina": "europe", "bulgaria": "europe",
    "croatia": "europe", "cyprus": "europe", "czech republic": "europe",
    "czechia": "europe", "denmark": "europe", "estonia": "europe",
    "finland": "europe", "france": "europe", "germany": "europe",
    "greece": "europe", "hungary": "europe", "iceland": "europe",
    "ireland": "europe", "italy": "europe", "kosovo": "europe",
    "latvia": "europe", "liechtenstein": "europe", "lithuania": "europe",
    "luxembourg": "europe", "malta": "europe", "moldova": "europe",
    "monaco": "europe", "montenegro": "europe", "netherlands": "europe",
    "north macedonia": "europe", "norway": "europe", "poland": "europe",
    "portugal": "europe", "romania": "europe", "russia": "europe",
    "san marino": "europe", "serbia": "europe", "slovakia": "europe",
    "slovenia": "europe", "spain": "europe", "sweden": "europe",
    "switzerland": "europe", "ukraine": "europe",
    "united kingdom": "europe", "vatican city": "europe",
    # ── Asia ────────────────────────────────────────────────────────
    "afghanistan": "asia", "armenia": "asia", "azerbaijan": "asia",
    "bangladesh": "asia", "bhutan": "asia", "brunei": "asia",
    "cambodia": "asia", "china": "asia", "georgia": "asia",
    "hong kong": "asia", "india": "asia", "indonesia": "asia",
    "japan": "asia", "kazakhstan": "asia", "kyrgyzstan": "asia",
    "laos": "asia", "macau": "asia", "malaysia": "asia",
    "maldives": "asia", "mongolia": "asia", "myanmar": "asia",
    "nepal": "asia", "north korea": "asia", "pakistan": "asia",
    "philippines": "asia", "singapore": "asia", "south korea": "asia",
    "sri lanka": "asia", "taiwan": "asia", "tajikistan": "asia",
    "thailand": "asia", "timor-leste": "asia", "turkmenistan": "asia",
    "uzbekistan": "asia", "vietnam": "asia",
    # ── Middle East ─────────────────────────────────────────────────
    "bahrain": "middle east", "iran": "middle east", "iraq": "middle east",
    "israel": "middle east", "jordan": "middle east",
    "kuwait": "middle east", "lebanon": "middle east",
    "oman": "middle east", "palestine": "middle east",
    "qatar": "middle east", "saudi arabia": "middle east",
    "syria": "middle east", "turkey": "middle east",
    "united arab emirates": "middle east", "yemen": "middle east",
    # ── Africa ──────────────────────────────────────────────────────
    "algeria": "africa", "angola": "africa", "benin": "africa",
    "botswana": "africa", "burkina faso": "africa", "burundi": "africa",
    "cabo verde": "africa", "cameroon": "africa",
    "central african republic": "africa", "chad": "africa",
    "comoros": "africa", "congo": "africa",
    "democratic republic of the congo": "africa", "djibouti": "africa",
    "egypt": "africa", "equatorial guinea": "africa", "eritrea": "africa",
    "eswatini": "africa", "ethiopia": "africa", "gabon": "africa",
    "gambia": "africa", "ghana": "africa", "guinea": "africa",
    "guinea-bissau": "africa", "ivory coast": "africa", "kenya": "africa",
    "lesotho": "africa", "liberia": "africa", "libya": "africa",
    "madagascar": "africa", "malawi": "africa", "mali": "africa",
    "mauritania": "africa", "mauritius": "africa", "morocco": "africa",
    "mozambique": "africa", "namibia": "africa", "niger": "africa",
    "nigeria": "africa", "rwanda": "africa", "senegal": "africa",
    "seychelles": "africa", "sierra leone": "africa", "somalia": "africa",
    "south africa": "africa", "south sudan": "africa", "sudan": "africa",
    "tanzania": "africa", "togo": "africa", "tunisia": "africa",
    "uganda": "africa", "zambia": "africa", "zimbabwe": "africa",
    # ── North America ───────────────────────────────────────────────
    "canada": "north america", "mexico": "north america",
    "united states": "north america",
    # ── Central America & Caribbean ─────────────────────────────────
    "bahamas": "central america & caribbean",
    "barbados": "central america & caribbean",
    "belize": "central america & caribbean",
    "costa rica": "central america & caribbean",
    "cuba": "central america & caribbean",
    "dominican republic": "central america & caribbean",
    "el salvador": "central america & caribbean",
    "guatemala": "central america & caribbean",
    "haiti": "central america & caribbean",
    "honduras": "central america & caribbean",
    "jamaica": "central america & caribbean",
    "nicaragua": "central america & caribbean",
    "panama": "central america & caribbean",
    "puerto rico": "central america & caribbean",
    "trinidad and tobago": "central america & caribbean",
    # ── South America ───────────────────────────────────────────────
    "argentina": "south america", "bolivia": "south america",
    "brazil": "south america", "chile": "south america",
    "colombia": "south america", "ecuador": "south america",
    "guyana": "south america", "paraguay": "south america",
    "peru": "south america", "suriname": "south america",
    "uruguay": "south america", "venezuela": "south america",
    # ── Oceania ─────────────────────────────────────────────────────
    "australia": "oceania", "fiji": "oceania", "new zealand": "oceania",
    "papua new guinea": "oceania", "samoa": "oceania", "tonga": "oceania",
}

# alias → canonical country name (both directions are handled in matching:
# the user may type the alias, or the event place may contain it)
ALIASES = {
    "usa": "united states", "us": "united states",
    "america": "united states", "u.s.": "united states",
    "u.s.a.": "united states", "states": "united states",
    "uk": "united kingdom", "great britain": "united kingdom",
    "britain": "united kingdom", "england": "united kingdom",
    "scotland": "united kingdom", "wales": "united kingdom",
    "northern ireland": "united kingdom",
    "uae": "united arab emirates", "emirates": "united arab emirates",
    "dubai": "united arab emirates", "abu dhabi": "united arab emirates",
    "sharjah": "united arab emirates",
    "ksa": "saudi arabia",
    "holland": "netherlands",
    "korea": "south korea", "republic of korea": "south korea",
    "prc": "china", "mainland china": "china",
    "türkiye": "turkey", "turkiye": "turkey",
    "czechia": "czech republic",
    "ivory coast": "ivory coast", "cote d'ivoire": "ivory coast",
    "côte d'ivoire": "ivory coast",
    "drc": "democratic republic of the congo",
    "burma": "myanmar",
    "east timor": "timor-leste",
    "swaziland": "eswatini",
    "cape verde": "cabo verde",
    "vietnam": "vietnam", "viet nam": "vietnam",
    "bharat": "india",
    "nippon": "japan",
    "aotearoa": "new zealand",
}

# region → member countries (built from COUNTRIES, then composites added)
REGIONS: dict = {}
for _c, _r in COUNTRIES.items():
    REGIONS.setdefault(_r, []).append(_c)

REGIONS["eu"] = REGIONS["europe"]
REGIONS["apac"] = REGIONS["asia"] + REGIONS["oceania"]
REGIONS["asia pacific"] = REGIONS["apac"]
REGIONS["emea"] = REGIONS["europe"] + REGIONS["middle east"] + REGIONS["africa"]
REGIONS["mena"] = REGIONS["middle east"] + ["egypt", "libya", "tunisia",
                                            "algeria", "morocco"]
REGIONS["gcc"] = ["bahrain", "kuwait", "oman", "qatar", "saudi arabia",
                  "united arab emirates"]
REGIONS["latin america"] = REGIONS["south america"] + \
    REGIONS["central america & caribbean"] + ["mexico"]
REGIONS["latam"] = REGIONS["latin america"]
REGIONS["caribbean"] = REGIONS["central america & caribbean"]
REGIONS["central america"] = REGIONS["central america & caribbean"]
REGIONS["americas"] = REGIONS["north america"] + REGIONS["latin america"]
REGIONS["southeast asia"] = ["brunei", "cambodia", "indonesia", "laos",
                             "malaysia", "myanmar", "philippines",
                             "singapore", "thailand", "timor-leste",
                             "vietnam"]
REGIONS["sea"] = REGIONS["southeast asia"]
REGIONS["asean"] = REGIONS["southeast asia"]
REGIONS["south asia"] = ["afghanistan", "bangladesh", "bhutan", "india",
                         "maldives", "nepal", "pakistan", "sri lanka"]
REGIONS["east asia"] = ["china", "hong kong", "japan", "macau", "mongolia",
                        "north korea", "south korea", "taiwan"]
REGIONS["central asia"] = ["kazakhstan", "kyrgyzstan", "tajikistan",
                           "turkmenistan", "uzbekistan"]
REGIONS["nordics"] = ["denmark", "finland", "iceland", "norway", "sweden"]
REGIONS["scandinavia"] = ["denmark", "norway", "sweden"]
REGIONS["dach"] = ["germany", "austria", "switzerland"]
REGIONS["benelux"] = ["belgium", "netherlands", "luxembourg"]
REGIONS["baltics"] = ["estonia", "latvia", "lithuania"]
REGIONS["iberia"] = ["spain", "portugal"]
REGIONS["balkans"] = ["albania", "bosnia and herzegovina", "bulgaria",
                      "croatia", "kosovo", "montenegro", "north macedonia",
                      "romania", "serbia", "slovenia"]
REGIONS["eastern europe"] = ["belarus", "bulgaria", "czech republic",
                             "hungary", "moldova", "poland", "romania",
                             "russia", "slovakia", "ukraine"]
REGIONS["western europe"] = ["austria", "belgium", "france", "germany",
                             "ireland", "luxembourg", "monaco",
                             "netherlands", "switzerland",
                             "united kingdom"]
REGIONS["southern europe"] = ["croatia", "cyprus", "greece", "italy",
                              "malta", "portugal", "slovenia", "spain"]
REGIONS["north africa"] = ["algeria", "egypt", "libya", "morocco",
                           "tunisia", "sudan"]
REGIONS["sub-saharan africa"] = [c for c in REGIONS["africa"]
                                 if c not in REGIONS["north africa"]]
REGIONS["oceania"] = REGIONS["oceania"] + ["new caledonia"]
REGIONS["anz"] = ["australia", "new zealand"]

# For each canonical country, every string the event's place text might
# use for it (the country itself + its aliases).
_COUNTRY_SURFACE_FORMS: dict = {c: [c] for c in COUNTRIES}
for _alias, _canon in ALIASES.items():
    if _canon in _COUNTRY_SURFACE_FORMS:
        _COUNTRY_SURFACE_FORMS[_canon].append(_alias)


def surface_forms(country: str) -> list:
    """All strings that may denote this country in a place text."""
    return _COUNTRY_SURFACE_FORMS.get(country, [country])


def resolve_geo_term(term: str):
    """Resolve a user-typed geo term.
    Returns (kind, match_terms):
      kind 'region'  → match_terms = every surface form of every member country
      kind 'country' → match_terms = surface forms of that country
      kind 'unknown' → match_terms = [term] (a city or unmapped spelling)
    """
    t = (term or "").strip().lower()
    if t in REGIONS:
        forms = []
        for c in REGIONS[t]:
            forms.extend(surface_forms(c))
        return "region", forms
    canon = ALIASES.get(t, t)
    if canon in COUNTRIES:
        return "country", surface_forms(canon)
    return "unknown", [t]
