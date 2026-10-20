"""Draw one deposited metal site: the ion, its first shell, and every bond.

Split in two on purpose. `viewer_spec` is pure -- dicts in, dicts out, no
browser, no network -- so the thing that decides *what* is drawn can be tested
offline. `site_viewer_html` only serialises that spec into a 3Dmol scene.

The scientifically load-bearing part of the picture is computed here, not in
the browser: every sphere and every bond is placed from the coordinates
`structure.binding_neighborhood` already measured, so the distance a user
reads off a bond is the same float the geometry-v2 table scored. The browser
re-parses the coordinate file only to draw context (cartoon, side-chain
sticks). If that context fails to match -- mmCIF chain identifiers can differ
between parsers -- the shell still draws correctly and the view degrades to
less context rather than to a wrong picture.
"""
import json
from pathlib import Path

from .structure import REE_LIGAND_CODES, donor_class

# Includes Y, which is not a lanthanide but is a rare earth and is screened as
# one; this set exists to colour the ion, not to make a periodic-table claim.
RARE_EARTH_ELEMENTS = frozenset(REE_LIGAND_CODES.values())

BACKGROUND = "#0c1424"
RARE_EARTH_COLOR = "#f5b544"
OTHER_METAL_COLOR = "#8fb8d0"

# One radius for every ion, deliberately. Ln3+ and Ca2+ ionic radii differ by
# only a few hundredths of an angstrom -- that near-identity is the whole
# selectivity problem -- so drawing them to scale would imply a distinction
# the chemistry does not offer. Colour carries identity instead.
METAL_RADIUS = 0.85
DONOR_RADIUS = 0.28
BOND_RADIUS = 0.055

# Keys are exactly structure.donor_class's return values.
DONOR_COLORS = {
    "carboxylate": "#e2574c",
    "backbone_carbonyl": "#e8954a",
    "sidechain_amide": "#a87fd0",
    "hydroxyl": "#4fb3a5",
    "water": "#6fa8dc",
    "ligand": "#c89bd6",
    "other": "#9aa5b1",
}
DONOR_LABELS = {
    "carboxylate": "Side-chain carboxylate O",
    "backbone_carbonyl": "Backbone carbonyl O",
    "sidechain_amide": "Side-chain amide O/N",
    "hydroxyl": "Hydroxyl O",
    "water": "Water",
    "ligand": "Other ligand",
    "other": "Other protein donor",
}
# Legend order, most to least diagnostic of a lanthanide site.
DONOR_ORDER = ("carboxylate", "backbone_carbonyl", "sidechain_amide",
               "hydroxyl", "water", "ligand", "other")

TMOL_SRC = "https://cdn.jsdelivr.net/npm/3dmol@2.5.5/build/3Dmol-min.js"
# Vendored copy, byte-identical to the npm tarball for 3dmol@2.5.5 (verified
# against the registry's published sha512) and served by Streamlit from
# ./static when server.enableStaticServing is on, which .streamlit/config.toml
# sets. BSD-3-Clause; the licence travels with it as static/3Dmol-LICENSE.txt.
VENDORED_TMOL_PATH = Path(__file__).resolve().parent.parent / "static" / "3Dmol-min.js"
VENDORED_TMOL_URL = "/app/static/3Dmol-min.js"


def tmol_sources() -> tuple[str, str]:
    """Where the page should load 3Dmol from, as (primary, fallback).

    Prefer the vendored copy, so a demo on a hostile or absent network still
    draws. Keep the CDN as a browser-side fallback rather than dropping it:
    static serving is a config option, and someone running `streamlit run`
    from another directory will not pick up our config.toml. Trying the local
    copy first and the CDN second means the viewer works if *either* is
    available, instead of trading one single point of failure for another.

    Returns an empty fallback when the vendored file is missing, which leaves
    the CDN as the only source and the existing "could not be loaded" message
    as the failure mode.
    """
    if VENDORED_TMOL_PATH.is_file():
        return VENDORED_TMOL_URL, TMOL_SRC
    return TMOL_SRC, ""


def metal_color(element: str) -> str:
    return RARE_EARTH_COLOR if (element or "").strip() in RARE_EARTH_ELEMENTS else OTHER_METAL_COLOR


def _xyz(source: dict, what: str) -> list[float]:
    coord = source.get("xyz")
    if not (isinstance(coord, (list, tuple)) and len(coord) == 3):
        raise ValueError(
            f"{what} carries no usable xyz. binding_neighborhood() supplies it; "
            "a site dict from an older cache will need re-parsing.")
    return [float(c) for c in coord]


def viewer_spec(site: dict, *, call: dict | None = None) -> dict:
    """Everything needed to draw one site, as plain JSON-safe data.

    Donor colouring goes through structure.donor_class rather than a private
    copy of the rules, so the legend counts here and the chemistry counts in
    the results table can never disagree about what a carboxylate is.
    """
    element = str(site.get("element", "")).strip()
    chain = str(site.get("chain", "")).strip()
    number = str(site.get("site", "")).strip()
    center = _xyz(site, "The metal site")

    donors, residues, seen = [], [], set()
    for donor in site.get("donors", []):
        cls = donor_class(donor)
        position = _xyz(donor, f"Donor {donor.get('atom')}")
        residue = str(donor.get("residue", "")).strip()
        resi = donor.get("residue_number")
        donors.append({
            "label": f"{residue}{resi}",
            "atom": str(donor.get("atom", "")).strip(),
            "element": str(donor.get("element", "")).strip(),
            "kind": donor.get("kind"),
            "donor_class": cls,
            "color": DONOR_COLORS.get(cls, DONOR_COLORS["other"]),
            "distance_A": donor.get("distance_A"),
            "xyz": position,
            # Midpoint, so the distance label sits on its own bond rather than
            # on top of the ion where ten of them would overlap.
            "midpoint": [round((a + b) / 2, 3) for a, b in zip(center, position)],
            "is_water": cls == "water",
        })
        key = (donor.get("chain"), resi)
        if key not in seen and donor.get("kind") == "protein":
            seen.add(key)
            residues.append({"chain": donor.get("chain"), "resi": resi})

    counts = {name: sum(1 for d in donors if d["donor_class"] == name) for name in DONOR_ORDER}
    legend = [{"donor_class": name, "label": DONOR_LABELS[name],
               "color": DONOR_COLORS[name], "count": counts[name]}
              for name in DONOR_ORDER if counts[name]]

    distances = [d["distance_A"] for d in donors if isinstance(d["distance_A"], (int, float))]
    pieces = [f"CN {site.get('coordination_number', len(donors))}"]
    for count, word in ((site.get("protein_donor_count"), "protein donor"),
                        (site.get("water_donor_count"), "water"),
                        (site.get("other_ligand_donor_count"), "other-ligand donor")):
        if count:
            pieces.append(f"{count} {word}{'' if count == 1 else 's'}")
    if distances:
        pieces.append(f"{min(distances):.2f}–{max(distances):.2f} Å")

    spec = {
        "title": f"{element} {number} · chain {chain}" if chain else f"{element} {number}",
        "element": element,
        "chain": chain,
        "site": number,
        "background": BACKGROUND,
        "metal": {"label": element, "xyz": center, "color": metal_color(element),
                  "radius": METAL_RADIUS},
        "donor_radius": DONOR_RADIUS,
        "bond_radius": BOND_RADIUS,
        "donors": donors,
        "residue_selection": residues,
        "legend": legend,
        "summary": " · ".join(pieces),
        "call": None,
    }
    if call:
        spec["call"] = {
            "call": call.get("call"),
            "reliable": call.get("call_reliable"),
            "score_version": call.get("score_version"),
            # A call drawn from asymmetric-unit coordinates can be missing half
            # its shell, so the badge must never read as settled when it is not.
            "text": f"{call.get('score_version', 'geometry')}: {call.get('call')}"
                    f"{'' if call.get('call_reliable') else ' (not reliable here)'}",
        }
    return spec


def _js(value) -> str:
    """JSON for embedding inside a <script> element.

    json.dumps alone is not enough: residue and chain identifiers come out of a
    deposited coordinate file, mmCIF does not bound their length the way the
    PDB column format does, and a literal `</script>` inside a JSON string
    would close the element early. Escaping the three HTML-significant
    characters is still valid JSON -- \\u003c inside a string is `<`.
    """
    return (json.dumps(value)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def _boot(fallback_src: str) -> str:
    """JS that runs `start()` as soon as $3Dmol exists, or `fail()` if it never does.

    The <script src> above has already resolved by the time this runs -- a
    classic script tag blocks the parser -- so `typeof $3Dmol` here is a
    reliable test of whether the primary source worked, and appending the
    fallback only on the failing path costs nothing on the happy one.
    """
    if not fallback_src:
        return "(typeof $3Dmol === 'undefined') ? fail() : start();"
    return f"""if (typeof $3Dmol !== 'undefined') {{
    start();
  }} else {{
    const s = document.createElement('script');
    s.src = {_js(fallback_src)};
    s.onload = function () {{ (typeof $3Dmol === 'undefined') ? fail() : start(); }};
    s.onerror = fail;
    document.head.appendChild(s);
  }}"""


def overview_html(coordinate_text: str, fmt: str, sites: list[dict] | None = None, *,
                  height: int = 460, script_src: str = TMOL_SRC,
                  fallback_src: str = "") -> str:
    """The whole fold, with every deposited metal marked and named.

    The orientation view. It answers "how many sites are there and where",
    which the per-site view deliberately crops away.
    """
    markers = [{"label": f"{s.get('element', '')} {s.get('site', '')}".strip(),
                "xyz": _xyz(s, "The metal site"),
                "color": metal_color(str(s.get("element", "")))}
               for s in (sites or [])]
    return f"""<div id="lantern-overview" style="width:100%;height:{height}px;
 background:{BACKGROUND};border-radius:12px;overflow:hidden"></div>
<script src="{script_src}"></script>
<script>
(function () {{
  const host = document.getElementById('lantern-overview');
  function fail() {{
    host.innerHTML = '<div style="padding:18px;color:#f0b5a8;font:13px -apple-system,sans-serif">'
      + '3Dmol.js could not be loaded, so the structure cannot be drawn.</div>';
  }}
  function start() {{
  const viewer = $3Dmol.createViewer(host, {{backgroundColor: {_js(BACKGROUND)}}});
  viewer.addModel({_js(coordinate_text)}, {_js(fmt)});
  viewer.setStyle({{}}, {{cartoon: {{color: 'spectrum', opacity: 0.85}}}});
  viewer.addStyle({{hetflag: true}}, {{sphere: {{scale: 0.3}}}});
  {_js(markers)}.forEach(function (mark) {{
    const p = {{x: mark.xyz[0], y: mark.xyz[1], z: mark.xyz[2]}};
    viewer.addSphere({{center: p, radius: {METAL_RADIUS}, color: mark.color}});
    viewer.addLabel(mark.label, {{position: p, fontSize: 11, fontColor: '#1b2330',
      backgroundColor: mark.color, backgroundOpacity: 0.95, borderThickness: 0,
      inFront: true}});
  }});
  viewer.zoomTo();
  viewer.render();
  }}

  {_boot(fallback_src)}
}})();
</script>"""


def site_viewer_html(coordinate_text: str, fmt: str, site: dict, *,
                     call: dict | None = None, height: int = 480,
                     script_src: str = TMOL_SRC, fallback_src: str = "") -> str:
    """A self-contained 3Dmol scene for one binding site.

    `fallback_src` is tried in the browser if `script_src` does not define
    $3Dmol, so a page served the vendored copy still draws when static
    serving is off. See `tmol_sources`.
    """
    spec = viewer_spec(site, call=call)
    return f"""<div id="lantern-site" style="position:relative;width:100%;height:{height}px;
 background:{BACKGROUND};border-radius:12px;overflow:hidden"></div>
<div id="lantern-controls" style="display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 4px">
</div>
<div id="lantern-legend" style="display:flex;flex-wrap:wrap;gap:10px;
 font:12px/1.5 -apple-system,Segoe UI,sans-serif;color:#b8c7d4"></div>
<script src="{script_src}"></script>
<script>
(function () {{
  const SPEC = {_js(spec)};
  const COORDS = {_js(coordinate_text)};
  const FMT = {_js(fmt)};
  const host = document.getElementById('lantern-site');

  function fail() {{
    // Say so rather than leaving a black rectangle: the numbers below the
    // viewer are computed server-side and remain valid without 3Dmol.
    host.innerHTML = '<div style="padding:18px;color:#f0b5a8;font:13px -apple-system,sans-serif">'
      + '3Dmol.js could not be loaded, so the structure cannot be drawn. '
      + 'The coordination numbers and distances below are computed server-side and are unaffected.</div>';
  }}

  function start() {{
  const viewer = $3Dmol.createViewer(host, {{backgroundColor: SPEC.background}});
  viewer.addModel(COORDS, FMT);
  const state = {{residues: true, distances: true, waters: true, cartoon: true}};

  function draw() {{
    viewer.removeAllShapes();
    viewer.removeAllLabels();
    viewer.setStyle({{}}, {{}});
    if (state.cartoon) {{
      viewer.setStyle({{}}, {{cartoon: {{color: '#4a5d70', opacity: 0.55}}}});
    }}
    if (SPEC.residue_selection.length) {{
      viewer.addStyle({{or: SPEC.residue_selection}},
                      {{stick: {{radius: 0.13, colorscheme: 'whiteCarbon'}}}});
    }}

    const m = SPEC.metal;
    viewer.addSphere({{center: {{x: m.xyz[0], y: m.xyz[1], z: m.xyz[2]}},
                      radius: m.radius, color: m.color}});
    viewer.addLabel(m.label, {{position: {{x: m.xyz[0], y: m.xyz[1], z: m.xyz[2]}},
      fontSize: 13, fontColor: '#1b2330', backgroundColor: m.color,
      backgroundOpacity: 0.95, borderThickness: 0, inFront: true}});

    SPEC.donors.forEach(function (d) {{
      if (d.is_water && !state.waters) return;
      const p = {{x: d.xyz[0], y: d.xyz[1], z: d.xyz[2]}};
      viewer.addCylinder({{start: {{x: m.xyz[0], y: m.xyz[1], z: m.xyz[2]}}, end: p,
        radius: SPEC.bond_radius, color: d.color, dashed: true,
        dashLength: 0.22, gapLength: 0.16, fromCap: 1, toCap: 1}});
      viewer.addSphere({{center: p, radius: SPEC.donor_radius, color: d.color}});
      if (state.residues) {{
        viewer.addLabel(d.label + ' ' + d.atom, {{position: p, fontSize: 10,
          fontColor: '#e8f1f8', backgroundColor: '#17202e', backgroundOpacity: 0.78,
          borderThickness: 0, inFront: true}});
      }}
      if (state.distances && d.distance_A !== null) {{
        viewer.addLabel(d.distance_A.toFixed(2), {{
          position: {{x: d.midpoint[0], y: d.midpoint[1], z: d.midpoint[2]}},
          fontSize: 10, fontColor: '#0c1424', backgroundColor: d.color,
          backgroundOpacity: 0.9, borderThickness: 0, inFront: true}});
      }}
    }});
    viewer.render();
  }}

  function frame() {{
    // Chain/residue identifiers can be numbered differently by the two
    // parsers in an mmCIF file. Falling back to the whole model keeps a
    // failed match from throwing away the scene.
    try {{
      if (!SPEC.residue_selection.length) throw new Error('no residues');
      viewer.zoomTo({{or: SPEC.residue_selection}});
    }} catch (err) {{
      viewer.zoomTo();
    }}
    viewer.zoom(0.9);
    viewer.render();
  }}

  const CONTROLS = [
    ['residues', 'Residue labels'], ['distances', 'Distances'],
    ['waters', 'Waters'], ['cartoon', 'Cartoon'],
  ];
  const bar = document.getElementById('lantern-controls');
  function style(button, on) {{
    button.style.cssText = 'cursor:pointer;border-radius:7px;padding:4px 10px;'
      + 'font:12px -apple-system,Segoe UI,sans-serif;border:1px solid #2d3f52;'
      + (on ? 'background:#1d4f63;color:#dff3f7' : 'background:#141d2b;color:#7f93a6');
  }}
  CONTROLS.forEach(function (pair) {{
    const button = document.createElement('button');
    button.textContent = pair[1];
    style(button, state[pair[0]]);
    button.onclick = function () {{
      state[pair[0]] = !state[pair[0]];
      style(button, state[pair[0]]);
      draw();
    }};
    bar.appendChild(button);
  }});
  const reset = document.createElement('button');
  reset.textContent = 'Reset view';
  style(reset, false);
  reset.onclick = frame;
  bar.appendChild(reset);

  const legend = document.getElementById('lantern-legend');
  [{{color: SPEC.metal.color, label: SPEC.metal.label + ' ion', count: null}}]
    .concat(SPEC.legend.map(function (entry) {{
      return {{color: entry.color, label: entry.label, count: entry.count}};
    }}))
    .forEach(function (entry) {{
      const row = document.createElement('span');
      const dot = document.createElement('span');
      dot.style.cssText = 'display:inline-block;width:10px;height:10px;border-radius:50%;'
        + 'margin-right:5px;background:' + entry.color;
      row.appendChild(dot);
      row.appendChild(document.createTextNode(
        entry.label + (entry.count === null ? '' : ' \\u00d7 ' + entry.count)));
      legend.appendChild(row);
    }});

  draw();
  frame();
  }}

  {_boot(fallback_src)}
}})();
</script>"""
