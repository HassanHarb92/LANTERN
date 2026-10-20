"""Offline tests for the binding-site viewer. No network, no browser.

They assert on the spec dict rather than on rendered HTML: the spec is what
decides which atoms are drawn and at what distance, and parsing JavaScript to
check that would test the string formatting instead of the chemistry.
"""
import json
import re
import shutil
import subprocess
import pytest

from lantern.structure import donor_class
from lantern.viewer import (DONOR_COLORS, DONOR_ORDER, OTHER_METAL_COLOR,
                            RARE_EARTH_COLOR, metal_color, overview_html,
                            site_viewer_html, viewer_spec)


def make_site(**overrides) -> dict:
    """A Nd site with one carboxylate, one backbone carbonyl and one water."""
    donors = [
        {"kind": "protein", "chain": "A", "residue_number": 58, "residue": "GLU",
         "atom": "OE1", "element": "O", "distance_A": 2.41, "xyz": [1.0, 0.0, 0.0]},
        {"kind": "protein", "chain": "A", "residue_number": 61, "residue": "ALA",
         "atom": "O", "element": "O", "distance_A": 2.55, "xyz": [0.0, 2.0, 0.0]},
        {"kind": "water", "chain": "A", "residue_number": 401, "residue": "HOH",
         "atom": "O", "element": "O", "distance_A": 2.70, "xyz": [0.0, 0.0, 3.0]},
    ]
    site = {"metal": "ND", "element": "Nd", "chain": "A", "site": "301",
            "xyz": [0.0, 0.0, 0.0], "coordination_number": 3,
            "protein_donor_count": 2, "water_donor_count": 1,
            "other_ligand_donor_count": 0, "mean_donor_distance_A": 2.55,
            "donors": donors}
    site.update(overrides)
    return site


class TestEveryDonorIsDrawn:
    """The coordination number in the table and the number of bonds in the
    picture are the same claim. A viewer that quietly drops a donor would
    show a CN-9 site as CN-8 while the table still called it lanthanide-like."""

    def test_one_entry_per_first_shell_donor(self):
        spec = viewer_spec(make_site())
        assert len(spec["donors"]) == 3

    def test_distances_are_the_measured_ones_not_recomputed(self):
        spec = viewer_spec(make_site())
        assert [d["distance_A"] for d in spec["donors"]] == [2.41, 2.55, 2.70]

    def test_metal_sits_at_the_deposited_position(self):
        spec = viewer_spec(make_site(xyz=[12.5, -3.25, 7.0]))
        assert spec["metal"]["xyz"] == [12.5, -3.25, 7.0]

    def test_bond_label_sits_between_ion_and_donor(self):
        spec = viewer_spec(make_site())
        assert spec["donors"][0]["midpoint"] == [0.5, 0.0, 0.0]

    def test_a_site_with_no_xyz_is_refused_rather_than_drawn_at_the_origin(self):
        site = make_site()
        del site["xyz"]
        with pytest.raises(ValueError, match="xyz"):
            viewer_spec(site)

    def test_a_donor_with_no_xyz_is_refused(self):
        site = make_site()
        del site["donors"][1]["xyz"]
        with pytest.raises(ValueError, match="xyz"):
            viewer_spec(site)


class TestColouringFollowsTheChemistry:
    """Colour is the legend's only claim, so it has to come from the same
    classifier the carboxylate and carbonyl counts come from."""

    def test_classes_match_structure_donor_class(self):
        site = make_site()
        spec = viewer_spec(site)
        assert [d["donor_class"] for d in spec["donors"]] == \
               [donor_class(d) for d in site["donors"]]

    def test_carboxylate_carbonyl_and_water_are_told_apart(self):
        spec = viewer_spec(make_site())
        assert [d["donor_class"] for d in spec["donors"]] == \
               ["carboxylate", "backbone_carbonyl", "water"]

    def test_every_class_has_a_colour(self):
        assert set(DONOR_ORDER) == set(DONOR_COLORS)

    def test_rare_earths_and_calcium_are_not_the_same_colour(self):
        assert metal_color("Nd") == RARE_EARTH_COLOR
        assert metal_color("Ca") == OTHER_METAL_COLOR
        assert metal_color("Ca") != metal_color("Nd")

    def test_yttrium_is_coloured_as_a_rare_earth(self):
        assert metal_color("Y") == RARE_EARTH_COLOR

    def test_legend_counts_match_the_donors_drawn(self):
        spec = viewer_spec(make_site())
        counted = {entry["donor_class"]: entry["count"] for entry in spec["legend"]}
        assert counted == {"carboxylate": 1, "backbone_carbonyl": 1, "water": 1}

    def test_legend_omits_classes_with_no_donors(self):
        spec = viewer_spec(make_site())
        assert "hydroxyl" not in {entry["donor_class"] for entry in spec["legend"]}


class TestWatersStayDistinguishable:
    """Waters are real first-shell donors and are counted, but a user
    comparing a Ln site with a Ca site needs to be able to take them out."""

    def test_waters_are_flagged_for_the_toggle(self):
        spec = viewer_spec(make_site())
        assert [d["is_water"] for d in spec["donors"]] == [False, False, True]

    def test_only_protein_residues_are_offered_for_stick_rendering(self):
        spec = viewer_spec(make_site())
        assert spec["residue_selection"] == [{"chain": "A", "resi": 58},
                                             {"chain": "A", "resi": 61}]

    def test_a_residue_donating_twice_is_selected_once(self):
        site = make_site()
        site["donors"].append({"kind": "protein", "chain": "A", "residue_number": 58,
                               "residue": "GLU", "atom": "OE2", "element": "O",
                               "distance_A": 2.6, "xyz": [1.0, 1.0, 0.0]})
        assert len(viewer_spec(site)["residue_selection"]) == 2


class TestSummaryAndCall:
    def test_summary_leads_with_coordination_number(self):
        assert viewer_spec(make_site())["summary"].startswith("CN 3")

    def test_summary_names_waters_separately_from_protein_donors(self):
        summary = viewer_spec(make_site())["summary"]
        assert "2 protein donors" in summary and "1 water" in summary

    def test_distance_range_is_reported(self):
        assert "2.41–2.70 Å" in viewer_spec(make_site())["summary"]

    def test_no_call_badge_without_a_call(self):
        assert viewer_spec(make_site())["call"] is None

    def test_an_unreliable_call_says_so_in_the_badge(self):
        spec = viewer_spec(make_site(), call={
            "call": "lanthanide-like", "call_reliable": False,
            "score_version": "geometry-v2"})
        assert "not reliable" in spec["call"]["text"]

    def test_a_reliable_call_is_not_hedged(self):
        spec = viewer_spec(make_site(), call={
            "call": "lanthanide-like", "call_reliable": True,
            "score_version": "geometry-v2"})
        assert "not reliable" not in spec["call"]["text"]


class TestUntrustedCoordinatesCannotBecomeMarkup:
    """Residue names, chain ids and the coordinate text all come out of a
    file fetched from RCSB. mmCIF does not bound their length the way the PDB
    column format does, so a literal </script> would close the element early
    and turn deposited data into page markup."""

    def test_a_script_tag_in_a_residue_name_is_escaped(self):
        site = make_site()
        site["donors"][0]["residue"] = "</script><img src=x onerror=alert(1)>"
        html = site_viewer_html("ATOM", "pdb", site)
        assert "</script><img" not in html
        assert "\\u003c/script\\u003e" in html

    def test_a_script_tag_in_the_coordinate_text_is_escaped(self):
        html = site_viewer_html("</script><script>alert(1)</script>", "pdb", make_site())
        assert html.count("</script>") == 2  # the two the template itself opens

    def test_overview_escapes_the_same_way(self):
        html = overview_html("</script><script>alert(1)</script>", "pdb", [make_site()])
        assert html.count("</script>") == 2

    def test_a_script_tag_in_the_format_name_is_escaped(self):
        html = site_viewer_html("ATOM", "</script><b>", make_site())
        assert "</script><b>" not in html


class TestTheSpecIsSerialisable:
    """It is embedded as a JSON literal, so a numpy float that survived
    structure.py would take the whole page down at render time rather than at
    parse time."""

    def test_spec_round_trips_through_json(self):
        spec = viewer_spec(make_site(), call={"call": "calcium-like",
                                              "call_reliable": True,
                                              "score_version": "geometry-v2"})
        assert json.loads(json.dumps(spec))["metal"]["xyz"] == [0.0, 0.0, 0.0]

    def test_html_names_the_pinned_3dmol_build(self):
        assert "3dmol@2.5.5" in site_viewer_html("ATOM", "pdb", make_site())

    def test_html_degrades_with_a_message_when_the_cdn_is_unavailable(self):
        assert "could not be loaded" in site_viewer_html("ATOM", "pdb", make_site())

    def test_overview_without_sites_still_renders(self):
        assert "addModel" in overview_html("ATOM", "pdb", [])


# Everything above tests the spec. The scene is only correct if the JavaScript
# then turns that spec into the right shapes, and a mistake there produces a
# blank viewer with no Python-side error -- the one failure mode a Streamlit
# smoke test cannot catch. So run the script for real against a recording stub
# and assert on the calls. Skipped rather than required: node is a developer
# convenience here, not a runtime dependency of the app.
HARNESS = """
const CALLS = {sphere: [], cylinder: [], label: [], zoomTo: 0, render: 0};
const BUTTONS = [];
function node(tag) {
  return {tag, style: {cssText: ''}, children: [], textContent: '', innerHTML: '',
    appendChild(c) { this.children.push(c); if (c.tag === 'button') BUTTONS.push(c); return c; }};
}
const nodes = {};
globalThis.document = {
  getElementById(id) { return nodes[id] || (nodes[id] = node('div')); },
  createElement(tag) { return node(tag); },
  createTextNode(t) { return {tag: '#text', textContent: t}; },
};
globalThis.$3Dmol = {createViewer: () => ({
  addModel() {}, setStyle() {}, addStyle() {}, zoom() {},
  addSphere(s) { CALLS.sphere.push(s); },
  addCylinder(c) { CALLS.cylinder.push(c); },
  addLabel(text) { CALLS.label.push(text); },
  removeAllShapes() { CALLS.sphere = []; CALLS.cylinder = []; },
  removeAllLabels() { CALLS.label = []; },
  zoomTo() { CALLS.zoomTo++; }, render() { CALLS.render++; },
})};
"""

PROBE = """
const report = () => ({bonds: CALLS.cylinder.length, spheres: CALLS.sphere.length,
  metal: CALLS.sphere[0].center, labels: CALLS.label.slice(),
  starts_at_ion: CALLS.cylinder.every(c => c.start.x === CALLS.sphere[0].center.x
    && c.start.y === CALLS.sphere[0].center.y && c.start.z === CALLS.sphere[0].center.z),
  ends: CALLS.cylinder.map(c => [c.end.x, c.end.y, c.end.z]),
  buttons: BUTTONS.map(b => b.textContent), zoomTo: CALLS.zoomTo, renders: CALLS.render});
const out = {initial: report()};
BUTTONS.find(b => b.textContent === 'Waters').onclick();
out.no_waters = report();
BUTTONS.find(b => b.textContent === 'Distances').onclick();
out.no_distances = report();
console.log(JSON.stringify(out));
"""


def run_scene(html: str) -> dict:
    """Execute the viewer's inline script under the stub and report the scene."""
    bodies = [b for b in re.findall(r"<script[^>]*>(.*?)</script>", html, re.S) if b.strip()]
    assert len(bodies) == 1, f"expected one inline script, found {len(bodies)}"
    done = subprocess.run(["node", "--input-type=module", "-e", HARNESS + bodies[0] + PROBE],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


@pytest.fixture(scope="module")
def scene():
    """One node run shared by the whole class; each assertion reads one fact."""
    return run_scene(site_viewer_html("ATOM", "pdb", make_site()))


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
class TestTheBrowserDrawsWhatTheSpecSays:
    def test_one_bond_per_donor(self, scene):
        assert scene["initial"]["bonds"] == 3

    def test_one_sphere_for_the_ion_and_one_per_donor(self, scene):
        assert scene["initial"]["spheres"] == 4

    def test_every_bond_starts_at_the_ion(self, scene):
        assert scene["initial"]["starts_at_ion"]

    def test_bonds_end_on_the_measured_donor_positions(self, scene):
        assert scene["initial"]["ends"] == [[1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 3.0]]

    def test_the_ion_is_drawn_where_it_was_deposited(self, scene):
        assert scene["initial"]["metal"] == {"x": 0.0, "y": 0.0, "z": 0.0}

    def test_measured_distances_reach_the_canvas(self, scene):
        assert {"2.41", "2.55", "2.70"} <= set(scene["initial"]["labels"])

    def test_donors_are_named_on_the_canvas(self, scene):
        assert "GLU58 OE1" in scene["initial"]["labels"]

    def test_the_view_is_framed_and_rendered(self, scene):
        assert scene["initial"]["zoomTo"] == 1 and scene["initial"]["renders"] > 0

    def test_hiding_waters_removes_exactly_the_water_bond(self, scene):
        assert scene["no_waters"]["bonds"] == 2
        assert [0.0, 0.0, 3.0] not in scene["no_waters"]["ends"]

    def test_hiding_distances_keeps_the_bonds(self, scene):
        assert scene["no_distances"]["bonds"] == scene["no_waters"]["bonds"]
        assert "2.41" not in scene["no_distances"]["labels"]

    def test_every_toggle_is_offered(self, scene):
        assert scene["initial"]["buttons"] == ["Residue labels", "Distances", "Waters",
                                               "Cartoon", "Reset view"]

    def test_the_overview_script_also_runs(self):
        html = overview_html("ATOM", "pdb", [make_site()])
        bodies = [b for b in re.findall(r"<script[^>]*>(.*?)</script>", html, re.S) if b.strip()]
        done = subprocess.run(["node", "--input-type=module", "-e",
                               HARNESS + bodies[0] + "console.log(CALLS.sphere.length)"],
                              capture_output=True, text=True, timeout=60)
        assert done.returncode == 0, done.stderr[:2000]
        assert done.stdout.strip() == "1"
