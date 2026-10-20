#!/usr/bin/env python3
"""Validate this repo's first-shell extraction against MetalPDB.

MetalPDB (`metalpdb.cerm.unifi.it`, *NAR* 2018, 10.1093/nar/gkx989) has
independently decomposed every PDB metal site into donors and coordination
number. Agreement between two implementations that share no code is the
strongest evidence available that `binding_neighborhood()` is reading
structures correctly -- and it costs one HTTP request per element.

WHAT AGREEMENT MEANS HERE, precisely. The two use different first-shell
radii: this repo takes O/N/S within 3.2 A, MetalPDB appears to cut nearer
3.0. So coordination numbers are *expected* to differ, and comparing them
directly would manufacture a disagreement out of a documented convention.
What must match is the donors themselves: every donor MetalPDB reports
should appear in this repo's list at the same distance, and every extra this
repo reports should lie in the band between the two cutoffs. A donor missing
from this repo's list, or a distance that disagrees, is a real defect.

The comparison is per metal ion, not per MetalPDB site. MetalPDB groups
nearby ions into one polymetallic site; this repo emits one site per ion. The
unit of comparison here is the ion, anchored on its element and residue
number so that site matching never depends on the distances under test.

The roadmap's caution is preserved: the API returns only a subset of the
sites `/stats` counts (it appears to expose protein-chain sites only), so
this is a check on the sites it does return, never a census. The two sources
are never mixed into one table.

Usage:
    python -I scripts/crosscheck_metalpdb.py                 # a few elements
    python -I scripts/crosscheck_metalpdb.py --elements Nd La Ce
"""
import argparse
import gzip
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests                                           # noqa: E402
from io import StringIO                                    # noqa: E402

from Bio.PDB.MMCIFParser import MMCIFParser                # noqa: E402

from lantern.structure import binding_neighborhood       # noqa: E402

CORPUS = ROOT / ".cache" / "corpus"
API = "https://metalpdb.cerm.unifi.it/api"
# Elements with few enough sites to check exhaustively and which matter most:
# Nd and Dy are the commercially critical pair, La and Ce the natural-biology
# ones. Gd/Yb/Tb are phasing bulk and would make this a load test.
DEFAULT_ELEMENTS = ("Nd", "La", "Ce", "Dy")
TOLERANCE_A = 0.05


def metalpdb_sites(element: str) -> list[dict]:
    response = requests.get(
        API, params={"query": f"metal:{element}",
                     "columns": "donors,coordination,geometry,ligands"},
        timeout=60, headers={"User-Agent": "LANTERN/0.1 (research)"})
    response.raise_for_status()
    return response.json()


def their_donors(metal: dict) -> list[tuple]:
    """(chain, residue, residue_number, atom, distance) for ONE MetalPDB metal.

    Per metal, not per site. A MetalPDB "site" is polymetallic: 4ll7_14 holds
    two Dy ions, resseq 201 with CN 7 and resseq 202 with CN 2, grouped
    because they are near each other. This repo reports one site per ion.
    The first version of this function flattened every metal's ligands into
    one list and compared that against a single local ion, which reports the
    *other* ion's donors as missing and its distances as disagreements --
    `E/GLU113 OE2 theirs 2.23 vs ours 2.62` was their distance to Dy202
    against this repo's distance to Dy201. Both numbers were right.

    The chain belongs in the key too. 5YTQ has five La ions across three
    copies of one subunit, so Glu15 OE1 exists in every chain at a slightly
    different distance; keyed without the chain, the matcher locked onto the
    wrong subunit and reported the 0.15 A offsets as parser defects.
    """
    out = []
    for ligand in metal.get("ligands", []):
        for donor in ligand.get("donors", []):
            out.append(((ligand.get("chain") or "").strip(),
                        ligand["residue"].strip().upper(),
                        ligand["residue_pdb_number"],
                        donor["atom"].strip().upper(),
                        round(float(donor["distance"]), 2)))
    return out


def our_sites(pdb_id: str) -> dict[tuple, dict]:
    """Every rare-earth site in one cached entry, keyed by (chain, resseq)."""
    path = CORPUS / f"{pdb_id.upper()}.cif.gz"
    if not path.exists():
        return {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        text = gzip.open(path, "rt", errors="replace").read()
        sites = binding_neighborhood(text, "cif")
    return {
        (site["chain"], site["site"]): {
            "element": (site["element"] or "").strip().upper(),
            "donors": [
                (d["chain"].strip(), d["residue"].strip().upper(),
                 d["residue_number"], d["atom"].strip().upper(), d["distance_A"])
                for d in site["donors"]]}
        for site in sites}


def residue_index(pdb_id: str) -> frozenset:
    """Every (chain, residue number) present in one cached entry.

    Used only to decide whether a MetalPDB label is stale. Parsed separately
    from `binding_neighborhood`, which returns sites rather than an inventory
    of the file.
    """
    path = CORPUS / f"{pdb_id.upper()}.cif.gz"
    if not path.exists():
        return frozenset()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        text = gzip.open(path, "rt", errors="replace").read()
        structure = MMCIFParser(QUIET=True).get_structure(pdb_id, StringIO(text))
    return frozenset((chain.id, str(residue.id[1]))
                     for model in structure for chain in model
                     for residue in chain)


def candidates(ours: dict[tuple, dict], metal: dict) -> dict[tuple, dict]:
    """Local sites that could be this MetalPDB metal: same element, same resseq.

    Anchoring on the metal's own residue number keeps site matching
    independent of the donor distances being compared -- picking the local
    site whose distances agree best and then reporting that distances agree
    would be circular. MetalPDB gives no chain for the metal itself, and its
    `atom_pdb_number` is not usable as a key: it reads PDB-format files whose
    serials differ from the mmCIF ones (4LL7's two ions are 5995/6140 there
    and 5987/6132 here), so resseq plus element is the strongest anchor
    available. 4LL7 numbers a Dy 201 in six different chains, so this can
    still return several, and donor *identity* -- never distance -- breaks
    the tie below.
    """
    symbol = (metal.get("symbol") or "").strip().upper()
    # str() on both sides deliberately: this repo carries the residue number
    # as the string "201" and MetalPDB as the integer 201, so == is False for
    # every ion in the corpus and the first run of this matcher reported all
    # 66 of them as unmatched -- a total failure that looks exactly like a
    # parser that found nothing.
    number = str(metal.get("residue_pdb_number")).strip()
    return {key: value for key, value in ours.items()
            if str(key[1]).strip() == number and value["element"] == symbol}


def compare(theirs: list[tuple], ours: list[tuple],
            present: frozenset = frozenset()) -> dict:
    """Match their donors into ours by (chain, residue, number, atom).

    With one allowance, for atoms the PDB has relabelled since MetalPDB was
    built. 5KKB's La711 is coordinated by a mannose that MetalPDB calls
    A/MAN709; the current mmCIF carries the same sugar as C/MAN5, because
    the carbohydrate remediation moved oligosaccharides into their own
    branched-entity chains and renumbered them (this entry's
    `_pdbx_branch_scheme` maps C/MAN5 back to auth chain A). Keyed on chain
    and number those donors look missing, and the first run reported them as
    parser defects.

    `present` is every (chain, residue number) in the current file, and it is
    what keeps the allowance honest. Without it the first version paired
    MetalPDB's 4LL7 G/GLU128 OE1 at 2.25 A with this repo's C/GLU113 OE1 at
    2.26 A and called them one atom. They are not: 4LL7 has eight NCS copies
    of one subunit, every chain contains both a Glu113 and a Glu128, and
    "same atom name at the same distance" is therefore guaranteed to recur in
    every copy -- the allowance was matching symmetry mates. A stale label is
    one that *no longer exists*, so the allowance now fires only when their
    (chain, number) is absent from the file. 4LL7's chain G really does have
    a residue 128, so their label stands and the pairing is refused.

    The rest of the test stays narrow: same residue name, same atom name,
    distance equal within tolerance, exactly one candidate. Relabelled donors
    are printed on their own line and counted separately, never folded
    silently into agreement -- an allowance that can hide a genuine miss has
    to stay visible.
    """
    index = {(c, r, n, a): d for c, r, n, a, d in ours}
    their_keys = {(c, r, n, a) for c, r, n, a, _ in theirs}
    extra = [(c, r, n, a, d) for c, r, n, a, d in ours
             if (c, r, n, a) not in their_keys]
    missing, mismatched, relabelled = [], [], []
    for chain, residue, number, atom, distance in theirs:
        ours_distance = index.get((chain, residue, number, atom))
        if ours_distance is None:
            stale = present and (chain, str(number)) not in present
            same = [e for e in extra if e[1] == residue and e[3] == atom
                    and abs(e[4] - distance) <= TOLERANCE_A] if stale else []
            if len(same) == 1:
                relabelled.append((chain, residue, number, atom, distance, same[0]))
                extra.remove(same[0])
            else:
                missing.append((chain, residue, number, atom, distance))
        elif abs(ours_distance - distance) > TOLERANCE_A:
            mismatched.append((chain, residue, number, atom, distance, ours_distance))
    return {"missing": missing, "mismatched": mismatched,
            "relabelled": relabelled, "extra": extra}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elements", nargs="+", default=list(DEFAULT_ELEMENTS))
    args = parser.parse_args()

    checked = agreed = relabelled = vacuous = 0
    all_extra, defects, skipped, unmatched = [], [], 0, 0
    inventory: dict[str, frozenset] = {}
    for element in args.elements:
        try:
            sites = metalpdb_sites(element)
        except Exception as error:                        # noqa: BLE001
            print(f"{element}: MetalPDB unreachable ({type(error).__name__}) "
                  f"-- skipped, not counted as agreement")
            continue
        by_entry: dict[str, list] = {}
        for site in sites:
            for metal in site.get("metals", []):
                by_entry.setdefault(site["site"].split("_")[0].upper(),
                                    []).append((site["site"], metal))
        metals = sum(len(group) for group in by_entry.values())
        print(f"\n{element}: MetalPDB returns {len(sites)} site(s), "
              f"{metals} metal ion(s)")
        for pdb_id, group in by_entry.items():
            ours = our_sites(pdb_id)
            present = inventory.setdefault(pdb_id, residue_index(pdb_id))
            if not ours:
                print(f"  {pdb_id} not in local corpus -- {len(group)} ion(s) "
                      f"skipped")
                skipped += len(group)
                continue
            # One local ion cannot be two of theirs, so ions are claimed as
            # they match and the claimed ones leave the pool. Processed
            # most-donors-first because an ion with nine donors identifies
            # itself and an ion with none cannot: 5YTQ has a La101 in three
            # chains, MetalPDB reports one of them with no ligands at all,
            # and the first version let that empty ion settle on chain A --
            # already matched, and the only one of the three with donors --
            # then reported chain A's five genuine donors as extras below
            # 2.9 A. The local chain C La101 it should have taken has no
            # donors either, so the two sources had agreed all along.
            claimed: set = set()
            for site_id, metal in sorted(group,
                                         key=lambda e: -len(their_donors(e[1]))):
                theirs = their_donors(metal)
                pool = {key: value
                        for key, value in candidates(ours, metal).items()
                        if key not in claimed}
                tag = f"{site_id}/{metal.get('symbol')}{metal.get('residue_pdb_number')}"
                if not pool:
                    # Not an agreement and not a defect: this repo may have
                    # read the ion under a chain or resseq the anchor cannot
                    # reach. Counted on its own line so it cannot be mistaken
                    # for either.
                    print(f"  {tag:18s} no local ion with that element and "
                          f"residue number -- unmatched")
                    unmatched += 1
                    continue
                # Several chains can carry the same resseq, so pick the
                # candidate sharing the most donor *identities* with theirs.
                # Scored on exact matches only -- relabelled ones are
                # subtracted back out. Counting them made a wrong-chain ion
                # in 4LL7 score as highly as the right one, because across
                # eight NCS copies the loose match always succeeds, and the
                # matcher then settled on the wrong subunit.
                # Seeded with the first candidate rather than None: when none
                # shares a single donor every option ties, a strict > never
                # fires, and the first version crashed on a None key instead
                # of honestly reporting every donor as missing.
                best_key, best = next(iter(pool)), None
                for key, value in pool.items():
                    result = compare(theirs, value["donors"], present)
                    shared = (len(theirs) - len(result["missing"])
                              - len(result["relabelled"]))
                    # Ties broken towards the candidate holding a similar
                    # number of donors, which is the only signal left when
                    # nothing is shared.
                    score = (shared, -abs(len(value["donors"]) - len(theirs)))
                    if best is None or score > best[0]:
                        best_key, best = key, (score, result)
                best = best[1]
                claimed.add(best_key)
                if not theirs:
                    # Counted apart from the agreements. Two sources both
                    # reporting nothing is not evidence that they would have
                    # reported the same something.
                    print(f"  {tag:18s} -> chain {best_key[0]} site {best_key[1]}"
                          f"  MetalPDB lists no donors -- nothing to check "
                          f"(ours: {len(ours[best_key]['donors'])})")
                    vacuous += 1
                    continue
                checked += 1
                ok = not best["missing"] and not best["mismatched"]
                agreed += ok
                relabelled += len(best["relabelled"])
                status = "agree" if ok else "DISAGREE"
                if ok and best["relabelled"]:
                    status = "agree (relabelled)"
                print(f"  {tag:18s} -> chain {best_key[0]} site {best_key[1]}"
                      f"  {len(theirs)} donors  {status}"
                      f"  (+{len(best['extra'])} beyond their cutoff)")
                for chain, residue, number, atom, distance, mine in best["relabelled"]:
                    print(f"      RELABELLED: their {chain}/{residue}{number} "
                          f"{atom} at {distance} A is our {mine[0]}/{mine[1]}"
                          f"{mine[2]} {mine[3]} at {mine[4]} A")
                for chain, residue, number, atom, distance in best["missing"]:
                    print(f"      MISSING from ours: {chain}/{residue}{number} "
                          f"{atom} at {distance} A")
                    defects.append((tag, chain, residue, number, atom))
                for chain, residue, number, atom, theirs_d, ours_d in best["mismatched"]:
                    print(f"      DISTANCE differs: {chain}/{residue}{number} "
                          f"{atom} theirs {theirs_d} vs ours {ours_d}")
                    defects.append((tag, chain, residue, number, atom))
                all_extra += [(tag, *donor) for donor in best["extra"]]

    print(f"\n{agreed}/{checked} metal ions agree on every donor MetalPDB reports"
          f"{f', {skipped} skipped' if skipped else ''}"
          f"{f', {unmatched} unmatched' if unmatched else ''}"
          f"{f', {vacuous} with no donors on their side' if vacuous else ''}.")
    if relabelled:
        print(f"{relabelled} donor(s) matched only after allowing for a PDB "
              f"relabelling\n  (same residue and atom name, same distance, "
              f"different chain/number).")
    if all_extra:
        distances = [row[-1] for row in all_extra]
        print(f"{len(all_extra)} extra donors found by this repo, "
              f"{min(distances):.2f}-{max(distances):.2f} A.")
        print("  These are the 3.0-3.2 A band: a wider cutoff, not a disagreement.")
        close = sorted((row for row in all_extra if row[-1] < 2.9),
                       key=lambda row: row[-1])
        if close:
            # Named, not just counted. A warning that says "worth a look"
            # without saying at what cannot be acted on, and the first
            # version of this block printed only the minimum distance.
            print(f"\n  WARNING: {len(close)} extra donor(s) below 2.9 A, too "
                  f"close to be a\n  cutoff artefact. Either MetalPDB omitted "
                  f"something it should have\n  reported, or this repo "
                  f"invented it. Each one, nearest first:")
            for tag, chain, residue, number, atom, distance in close:
                print(f"    {tag:18s} {chain}/{residue}{number} {atom} "
                      f"at {distance} A")
    return 0 if agreed == checked else 1


if __name__ == "__main__":
    raise SystemExit(main())
