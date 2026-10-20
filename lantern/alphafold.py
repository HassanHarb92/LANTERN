"""Predicted models retrieved from the AlphaFold Protein Structure Database.

**NOTHING IN THIS MODULE RUNS ALPHAFOLD.** AlphaFold2 inference is a GPU job
with an MSA pipeline attached; it is not a web-app feature and pretending
otherwise would be the single most misleading thing this project could say.
What this module does is *download a model somebody else already computed*
from EBI's AlphaFold DB, which holds predictions for essentially all of
UniProt and serves them free over a REST API. Every record it returns is
labelled `evidence=EVIDENCE` and `experimental=False` for that reason, and the
word used throughout is "retrieved", never "ran" and never "predicted by us".

**The line this module must not blur.** `structure.py` fetches *experimental*
coordinates from RCSB: atoms somebody measured. This fetches a *prediction*:
atoms a neural network proposed. ROADMAP 2094 names the specific trap --
"AlphaFold apo models do not represent the metal-bound conformation" -- so a
predicted LanM homolog has no metal in it, cannot have its first shell read
off the way 8FNS can, and any site called on one is a hypothesis. The two
caches are deliberately separate directories so a file can never be mistaken
for the other kind by whatever picks it up.

**Where models land, and why not `data/structures/`.** `.cache/alphafold/`,
gitignored, for the same reason `scripts/download_corpus.py` puts Corpus A in
`.cache/corpus/`: `data/structures/` holds five hand-picked entries that are
*meant* to be committed so tests run offline, and the 188 LanM homologs of M4
are a few hundred megabytes of third-party coordinates that are not. The cache
also keeps repeat calls offline, which is the only reason a Streamlit app can
touch this at all without a round trip per rerun.

**Verified against the live service on 2026-10-20** rather than from memory:

  GET https://alphafold.ebi.ac.uk/api/prediction/C5B164
      -> 200, a JSON *array* of one object. Field names as spelled by the API:
         entryId "AF-C5B164-F1", modelCreatedDate "2025-08-01T00:00:00Z",
         latestVersion 6, allVersions [2,3,4,5,6], globalMetricValue 83.94,
         fractionPlddtVeryLow/Low/Confident/VeryHigh 0.105/0.113/0.150/0.632,
         pdbUrl, cifUrl, bcifUrl, paeDocUrl, plddtDocUrl, uniprotAccession,
         organismScientificName, sequence, isComplex.
  GET .../api/prediction/A0A4V2JDD3  -> 200, globalMetricValue 88.25 (Hans-LanM,
         the project's held-out positive control).
  GET .../api/prediction/P62158      -> **404, body `{}`**. P62158 is a
         demerged calmodulin accession; the live human CaM entries (P0DP23 and
         siblings) answer 200. A 404 is therefore a routine, expected answer
         about a perfectly real protein, not a service fault -- which is
         exactly why it must raise rather than yield an empty-looking record.
  GET .../api/prediction/Q8WZ42      -> 404. Titin is over the length AlphaFold
         DB models, so "AlphaFold DB covers all of UniProt" is not literally
         true and code here must not assume coverage.
  GET .../api/prediction/<nonsense>  -> 400 {"error": "Invalid identifier
         format..."}, so a malformed accession is caught locally instead.

Official endpoint description: https://alphafold.ebi.ac.uk/api/openapi.json,
`GET /prediction/{qualifier}`, response schema `NewEntrySummary`, which marks
`globalMetricValue` required and `pdbUrl`/`cifUrl` optional. Underlying method:
Jumper et al., Nature 596, 583 (2021), doi:10.1038/s41586-021-03819-2.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import requests

API_BASE = "https://alphafold.ebi.ac.uk/api/prediction"

# Gitignored (`.cache/` is in .gitignore), separate from data/structures/ so a
# predicted model and an experimental one can never be picked up interchangeably.
MODEL_CACHE = Path(__file__).resolve().parent.parent / ".cache" / "alphafold"

# Same courtesy header scripts/download_corpus.py sends RCSB. EBI serves these
# files from a CDN that answered a bare curl with 403 on 2026-10-20 while
# answering python-requests' default agent with 200, so an explicit, honest
# agent string is cheaper than debugging that twice.
USER_AGENT = "LANTERN/0.1 (research; contact via repository)"

# Stamped onto every record. The phrasing is load-bearing: callers render it,
# and the project's scientific contract forbids a predicted model reading as a
# measurement.
EVIDENCE = ("predicted model retrieved from AlphaFold DB (EBI); computational "
            "prediction, not an experimental structure, and not run here")

# AlphaFold confidence bands, from EMBL-EBI's own training material
# ("pLDDT: understanding local confidence",
# ebi.ac.uk/training/online/courses/alphafold/): very high > 90, confident
# 90-70, low 70-50, very low < 50.
#
# The bin edge *values* were not taken on trust either. Binning the 133
# residue pLDDTs of AF-C5B164-F1-model_v6.pdb with half-open bins [-inf,50)
# [50,70) [70,90) [90,inf) reproduces the four fraction fields the API
# publishes for that entry exactly (0.105 / 0.113 / 0.150 / 0.632).
#
# What that experiment does NOT establish is which side of each edge is
# inclusive: not one of the 133 residues sits exactly on 50.00, 70.00 or
# 90.00, so every assignment of the boundaries gives the same four fractions
# and the test cannot distinguish them. Half-open-upward is the convention
# EBI's prose implies ("above 90", "between 70 and 90") and it is what
# confidence_band() implements, but a residue at exactly 70.00 is a guess
# this module is making, not a fact it has checked.
PLDDT_VERY_HIGH = 90.0
PLDDT_CONFIDENT = 70.0
PLDDT_LOW = 50.0

# The gate's default floor. EBI: above 70 "usually corresponds to a correct
# backbone prediction with misplacement of some side chains"; below it the
# local backbone itself is not reliable, so a coordination geometry measured
# there is measuring nothing.
GATE_MINIMUM_PLDDT = PLDDT_CONFIDENT

# And the floor that would actually be needed to believe donor *atoms*. EBI
# reserves "both the backbone and side chains are typically predicted with high
# accuracy" for pLDDT > 90. geometry-v2 counts side-chain carboxylate oxygens
# at 2.3-2.6 A, so clearing GATE_MINIMUM_PLDDT makes a region eligible to be
# scored and does NOT make its donor distances trustworthy. The gate reports
# both and says so in its caveats rather than collapsing them into one pass.
SIDECHAIN_RELIABLE_PLDDT = PLDDT_VERY_HIGH

# The verdict string M4 requires. ROADMAP M4: "Gate on local pLDDT: a low-
# confidence region yields not_scored, not a low score." These are different
# claims -- "scored low" says the geometry was measured and is unlike a
# lanthanide site; "not_scored" says the geometry was never legible. Collapsing
# the second into a 0 would manufacture a negative result out of ignorance.
NOT_SCORED = "not_scored"
SCORABLE = "scorable"

# How far the mean recomputed from a coordinate file may sit from the API's
# globalMetricValue before the pair is treated as inconsistent.
#
# They do not agree to the last digit, and the reason is worth knowing: the
# B-factor column stores each residue's pLDDT rounded to 2 dp, while the
# published global figure is computed before that rounding. Measured on
# 2026-10-20: C5B164 reports 83.94 against a residue mean of 83.9453 (-0.0053)
# and A0A4V2JDD3 reports 88.25 against 88.2236 (+0.0264). So the gap is a few
# hundredths for the same model, and 0.5 is loose enough for that while still
# catching a cached file left over from an earlier model version.
MEAN_PLDDT_TOLERANCE = 0.5

# How far apart two atoms of one residue may be in B before the column stops
# looking like pLDDT. AlphaFold writes the identical value to every atom, so
# the honest tolerance is zero; this allows only for the 0.01 of the PDB
# B-factor field's own printed precision.
PLDDT_CONSTANT_TOLERANCE = 0.011

# UniProt's own accession pattern, from
# https://www.uniprot.org/help/accession_numbers. Checked locally so a typo
# raises here instead of being spent on a request the API answers with 400.
_ACCESSION = re.compile(
    r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]"
    r"|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$")


class AlphaFoldError(RuntimeError):
    """Any failure to obtain a usable predicted model.

    Every path out of this module is either a complete record or one of these.
    There is deliberately no "empty record" or "pLDDT 0.0" fallback: a stub
    that reached a ranking table would read as a real, very bad model.
    """


class NoModelAvailable(AlphaFoldError):
    """AlphaFold DB holds no model for this accession (HTTP 404, or an empty
    result list). A routine answer -- demerged accessions and sequences past
    the length limit both land here -- and still not something to paper over.
    """


class AlphaFoldUnavailable(AlphaFoldError):
    """The service could not be reached, or answered with an HTTP error other
    than 404. Distinct from NoModelAvailable because "we do not know" and
    "there is no model" are different facts about the protein."""


class MalformedPrediction(AlphaFoldError):
    """A response arrived but could not be trusted: unparseable JSON, a payload
    shape the API does not document, a missing required field, coordinates with
    no ATOM records, or a cached file whose pLDDT disagrees with its metadata."""


def valid_accession(accession: str) -> str:
    """Uppercase the accession after checking it is shaped like a UniProt one.

    Mirrors `structure._valid_id`: reject locally rather than spend a request
    discovering the API's 400. Lowercase input is accepted and normalised --
    the live API accepts `c5b164` -- because rejecting a user's shift key is
    not a scientific judgement.
    """
    text = (accession or "").strip().upper()
    if not _ACCESSION.match(text):
        raise ValueError(
            f"{accession!r} is not a UniProt accession "
            "(see https://www.uniprot.org/help/accession_numbers)")
    return text


def confidence_band(plddt: float) -> str:
    """Which AlphaFold band one pLDDT value falls in.

    Returns "very_high", "confident", "low" or "very_low". Band edges are
    EBI's; see the PLDDT_* constants for how they were confirmed rather than
    assumed.
    """
    value = float(plddt)
    if value >= PLDDT_VERY_HIGH:
        return "very_high"
    if value >= PLDDT_CONFIDENT:
        return "confident"
    if value >= PLDDT_LOW:
        return "low"
    return "very_low"


def _model_url(metadata: dict) -> tuple[str, str]:
    """The coordinate file to download, preferring legacy PDB.

    `pdbUrl` and `cifUrl` are both optional in the published schema, so the
    absence of one is not a bug but the absence of both is an unusable record.
    PDB is preferred only because the B-factor column is trivially parseable;
    mmCIF carries the same per-residue values in `_atom_site.B_iso_or_equiv`.
    """
    for key, suffix in (("pdbUrl", "pdb"), ("cifUrl", "cif")):
        url = metadata.get(key)
        if isinstance(url, str) and url:
            return url, suffix
    raise MalformedPrediction(
        f"AlphaFold DB record {metadata.get('entryId', '?')} carries neither "
        "pdbUrl nor cifUrl, so there is no model to retrieve.")


def _require(metadata: dict, field: str, accession: str):
    value = metadata.get(field)
    if value is None:
        raise MalformedPrediction(
            f"AlphaFold DB response for {accession} has no {field!r}; the "
            "documented schema requires it, so the record is not usable.")
    return value


def prediction_metadata(accession: str, *, timeout: int = 25) -> dict:
    """The AlphaFold DB record for one accession, validated, no file download.

    Fails closed on every branch -- see the module docstring for the live
    responses each branch was written against.

    Refuses a payload carrying more than one entry rather than silently taking
    the first. Multi-entry payloads mean fragmented models (very long chains)
    or complexes, and this module's per-residue pLDDT reader assumes one
    continuous single-chain model; picking entry [0] would quietly score a
    fragment as if it were the protein.
    """
    code = valid_accession(accession)
    url = f"{API_BASE}/{code}"
    try:
        response = requests.get(
            url, timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    except requests.RequestException as exc:
        raise AlphaFoldUnavailable(
            f"AlphaFold DB unreachable for {code} ({type(exc).__name__}). "
            "No model was retrieved; this is not evidence of absence.") from exc

    if response.status_code == 404:
        raise NoModelAvailable(
            f"AlphaFold DB has no predicted model for {code} (HTTP 404). "
            "Demerged or withdrawn accessions and sequences past the modelled "
            "length limit both answer this way.")
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AlphaFoldUnavailable(
            f"AlphaFold DB returned HTTP {response.status_code} for {code}.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise MalformedPrediction(
            f"AlphaFold DB returned unparseable JSON for {code}.") from exc

    # Shape first, emptiness second. The other order turns an undocumented
    # object body -- `{}`, or an error envelope the service might start
    # sending -- into the definite claim "no model exists for this protein",
    # which is a different and much more actionable statement than "the
    # service answered something this module does not understand".
    if not isinstance(payload, list):
        raise MalformedPrediction(
            f"AlphaFold DB returned {type(payload).__name__} for {code}; the "
            "documented schema is an array of prediction objects.")
    # An empty array is the same fact as a 404.
    if not payload:
        raise NoModelAvailable(
            f"AlphaFold DB returned an empty result for {code}: no model.")
    if len(payload) != 1:
        raise MalformedPrediction(
            f"AlphaFold DB returned {len(payload)} entries for {code}. This "
            "module handles single-chain, unfragmented monomer models only; "
            "fragments and complexes need their own handling, not entry [0].")

    metadata = payload[0]
    if not isinstance(metadata, dict):
        raise MalformedPrediction(
            f"AlphaFold DB entry for {code} is not an object.")
    if metadata.get("isComplex"):
        raise MalformedPrediction(
            f"AlphaFold DB entry for {code} is a complex; the per-residue "
            "pLDDT reader here assumes one chain and would mis-key it.")

    returned = str(_require(metadata, "uniprotAccession", code)).upper()
    if returned != code:
        raise MalformedPrediction(
            f"Asked AlphaFold DB for {code} and the record says {returned}.")

    score = _require(metadata, "globalMetricValue", code)
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise MalformedPrediction(
            f"globalMetricValue for {code} is {score!r}, not a number.")
    for field in ("entryId", "latestVersion", "modelCreatedDate"):
        _require(metadata, field, code)
    _model_url(metadata)  # raises if neither coordinate URL is present
    return metadata


class NotAPredictedModel(MalformedPrediction):
    """The file is not an AlphaFold DB model, so its B-factors are not pLDDT.

    A subclass of MalformedPrediction so that an existing
    `except MalformedPrediction` or `except AlphaFoldError` still covers it.
    """


# A predicted model says so in its own text. AlphaFold DB writes
# "TITLE     ALPHAFOLD MONOMER V2.0 PREDICTION FOR ..." into its PDB files and
# `_database_2.database_id AlphaFoldDB` plus an `_ma_qa_metric` block into its
# mmCIF; neither string occurs anywhere in an RCSB experimental entry (checked
# against 8FNS, 9PI2, 1CLL). Only the file's head is scanned, so this costs a
# few kilobytes rather than a parse.
_PREDICTION_MARKERS = ("ALPHAFOLD", "_MA_QA_METRIC")
_MARKER_SCAN_BYTES = 65536


def _looks_predicted(path: Path) -> bool:
    """True if the file's own header says it is an AlphaFold model."""
    try:
        head = path.open("rb").read(_MARKER_SCAN_BYTES).decode("utf-8", "replace").upper()
    except OSError:
        return False
    return any(marker in head for marker in _PREDICTION_MARKERS)


def _parse_model(path: Path):
    """One Bio.PDB structure from a cached AlphaFold coordinate file."""
    from Bio.PDB import MMCIFParser, PDBParser

    parser = (MMCIFParser(QUIET=True) if path.suffix.lower() == ".cif"
              else PDBParser(QUIET=True))
    return parser.get_structure("model", str(path))


def residue_plddt(model_file: Path | str) -> dict[int, float]:
    """Per-residue pLDDT, keyed by residue number, read from the B-factor column.

    AlphaFold DB stores the per-residue confidence in the B-factor field of its
    PDB and mmCIF files, writing the same value to every atom of a residue.
    For AF-C5B164-F1-model_v6.pdb all 133 residues carry a constant B across
    their atoms, and the resulting per-residue series is *identical*, value for
    value, to the `confidenceScore` array in the entry's own confidence JSON
    (AF-C5B164-F1-confidence_v6.json). The first atom's value is therefore the
    residue's pLDDT.

    **The B-factor column only means pLDDT in a predicted model.** In an
    experimental structure the same column is a temperature factor, and
    nothing about reading it raises an error: this function used to accept
    `data/structures/8FNS.pdb` -- a 1.01 A X-ray structure -- and return its
    crystallographic B-factors as "pLDDT", which site_confidence() would then
    gate on and report as a confidence verdict about a measured structure.
    That is the worst class of bug this project can have, because the output
    is a plausible number of the right magnitude with a completely wrong
    meaning. So provenance is now checked twice, and both checks must pass:

      1. The file says what it is. AlphaFold DB writes "ALPHAFOLD" into the
         TITLE of its PDB files and an `_ma_qa_metric` block into its mmCIF.
         Neither string appears in 8FNS, 9PI2 or 1CLL.
      2. The B-factors behave like pLDDT: constant across every atom of a
         residue, and inside 0-100. Measured on the three experimental entries
         in data/structures/, *every* residue has a non-constant B (105/105,
         111/111, 143/143), so this alone separates the two kinds -- but it is
         the weaker test, because a low-resolution structure refined with
         grouped B-factors could pass it. Hence check 1 as well.

    Check 2 is also the invariant this docstring claims in its first paragraph.
    It was verified once by hand and then never enforced at runtime, so a model
    that violated it would have been read one atom at a time without complaint.

    Single chain only. Raises on anything else rather than flattening two
    chains into one residue-number space, where residue 37 of chain B would
    silently overwrite residue 37 of chain A.
    """
    path = Path(model_file)
    if not path.exists():
        raise MalformedPrediction(f"No coordinate file at {path}")
    if not _looks_predicted(path):
        raise NotAPredictedModel(
            f"{path.name} carries no AlphaFold marker in its header, so its "
            "B-factor column is a crystallographic temperature factor and not "
            "pLDDT. Reading it as confidence would attach a prediction-quality "
            "verdict to measured coordinates. Experimental structures belong "
            "to structure.py; this module reads AlphaFold DB models only.")
    model = next(_parse_model(path).get_models())
    chains = [c for c in model]
    if len(chains) != 1:
        raise MalformedPrediction(
            f"{path.name} has {len(chains)} chains; this reader handles the "
            "single-chain monomer models AlphaFold DB serves for UniProt.")
    scores: dict[int, float] = {}
    varying: list[int] = []
    for residue in chains[0]:
        if residue.id[0] != " ":
            continue  # no heteroatoms in an AlphaFold model, but do not rely on it
        values = [float(a.get_bfactor()) for a in residue]
        if not values:
            continue
        if max(values) - min(values) > PLDDT_CONSTANT_TOLERANCE:
            varying.append(residue.id[1])
        scores[residue.id[1]] = values[0]
    if not scores:
        raise MalformedPrediction(f"{path.name} contains no residues to read pLDDT from.")
    if varying:
        raise NotAPredictedModel(
            f"{path.name} has {len(varying)} residues whose atoms disagree on "
            f"their B-factor (first: {varying[:5]}). pLDDT is a per-residue "
            "score written identically to every atom, so this column is not "
            "pLDDT and must not be read as confidence.")
    out_of_range = {n: v for n, v in scores.items() if not 0.0 <= v <= 100.0}
    if out_of_range:
        raise NotAPredictedModel(
            f"{path.name} has B-factors outside the 0-100 pLDDT range "
            f"({dict(list(out_of_range.items())[:3])}); this column is not pLDDT.")
    return scores


def mean_plddt(model_file: Path | str) -> float:
    """Mean pLDDT over residues, not over atoms.

    The distinction is not pedantry. For AF-C5B164-F1-model_v6 the residue-level
    mean is 83.9453, against the 83.94 AlphaFold DB publishes as
    `globalMetricValue`; the atom-level mean is 84.2173, which is a quarter of
    a point out, because residues differ in atom count and an atom mean
    therefore weights large side chains more heavily. Only the residue-level
    figure is comparable to the number the database reports.
    """
    scores = residue_plddt(model_file)
    return sum(scores.values()) / len(scores)


def _record(metadata: dict, path: Path) -> dict:
    """Assemble the public record and cross-check the file against the metadata.

    `mean_plddt` is taken from the API's `globalMetricValue`, not from the file.
    Both were computed and they agree to a few hundredths (see
    MEAN_PLDDT_TOLERANCE for the measured gaps and why they are not zero), and
    the API figure is preferred for being the authoritative one: it is what the
    database publishes, what its website shows, and what any other tool
    comparing against this record will have. The file-derived figure is kept
    beside it as `mean_plddt_from_file` and the two are required to agree --
    that check is what catches a cached coordinate file left behind by an
    earlier model version, which is otherwise a silent, plausible-looking
    wrong answer.
    """
    accession = str(metadata["uniprotAccession"]).upper()
    reported = float(metadata["globalMetricValue"])
    computed = mean_plddt(path)
    if abs(reported - computed) > MEAN_PLDDT_TOLERANCE:
        raise MalformedPrediction(
            f"{path.name} has mean pLDDT {computed:.2f} but the AlphaFold DB "
            f"record for {accession} reports {reported:.2f}. The file and the "
            "metadata describe different models; delete the cache entry.")
    url, _ = _model_url(metadata)
    return {
        "accession": accession,
        "entry_id": metadata["entryId"],
        "model_path": str(path),
        "model_version": metadata["latestVersion"],
        "model_created": metadata["modelCreatedDate"],
        "source_url": url,
        "api_url": f"{API_BASE}/{accession}",
        "mean_plddt": round(reported, 2),
        "mean_plddt_from_file": round(computed, 2),
        "mean_plddt_source": "AlphaFold DB globalMetricValue (API)",
        "mean_plddt_band": confidence_band(reported),
        # The four published band fractions, passed through under readable
        # names. Reported because a mean of 83.94 can hide a disordered tail:
        # this entry is 63% very-high and still 10.5% very-low.
        "plddt_band_fractions": {
            "very_low": metadata.get("fractionPlddtVeryLow"),
            "low": metadata.get("fractionPlddtLow"),
            "confident": metadata.get("fractionPlddtConfident"),
            "very_high": metadata.get("fractionPlddtVeryHigh"),
        },
        "organism": metadata.get("organismScientificName"),
        "description": metadata.get("uniprotDescription"),
        "sequence": metadata.get("sequence", ""),
        "method": metadata.get("toolUsed"),
        # The two fields nothing downstream may lose.
        "experimental": False,
        "evidence": EVIDENCE,
    }


def _cache_paths(accession: str, cache_dir: Path | None) -> tuple[Path, Path]:
    root = Path(cache_dir) if cache_dir is not None else MODEL_CACHE
    return root, root / f"{accession}.json"


def cached_model(accession: str, *, cache_dir: Path | None = None) -> dict | None:
    """A previously fetched record, or None if this accession was never fetched.

    A cache entry counts only when *both* halves are present -- the metadata
    JSON and the coordinate file it names. A metadata file pointing at a
    coordinate file that is gone is a miss, not a record, which is why
    `fetch_model` writes the coordinates first and the metadata last.
    """
    code = valid_accession(accession)
    _, meta_path = _cache_paths(code, cache_dir)
    if not meta_path.exists():
        return None
    try:
        metadata = json.loads(meta_path.read_text())
    except ValueError as exc:
        raise MalformedPrediction(
            f"Cached AlphaFold metadata at {meta_path} is not valid JSON; "
            "delete it and re-fetch.") from exc
    if not isinstance(metadata, dict):
        raise MalformedPrediction(
            f"Cached AlphaFold metadata at {meta_path} is a "
            f"{type(metadata).__name__}, not a prediction record.")
    # The filename says one accession and the record inside says another only
    # if something went wrong -- a hand-edited cache, an interrupted write, a
    # directory copied between accessions. Whatever the cause, serving it
    # would answer a question about C5B164 with A0A4V2JDD3's model and keep
    # doing so for every later call, because nothing downstream re-checks.
    # prediction_metadata() makes this exact check on the fetch path; the
    # cache is the half that actually persists the mistake.
    filed_as = str(metadata.get("uniprotAccession", "")).upper()
    if filed_as != code:
        raise MalformedPrediction(
            f"Cached AlphaFold metadata at {meta_path} is filed under {code} "
            f"but describes {filed_as or 'no accession'}. Delete it and "
            "re-fetch; serving it would return the wrong protein's model.")
    model_file = meta_path.parent / str(metadata.get("_lantern_model_file", ""))
    if not metadata.get("_lantern_model_file") or not model_file.exists():
        return None
    try:
        return _record(metadata, model_file)
    except KeyError as exc:
        # Only reachable if the cache was edited by hand or truncated: every
        # entry fetch_model writes has already passed prediction_metadata.
        # Raised as a module error anyway, so a caller's `except AlphaFoldError`
        # covers a damaged cache as well as a damaged response.
        raise MalformedPrediction(
            f"Cached AlphaFold metadata at {meta_path} has no {exc.args[0]!r}; "
            "it is not a complete record. Delete it and re-fetch.") from exc


def fetch_model(accession: str, *, timeout: int = 25, use_cache: bool = True,
                cache_dir: Path | None = None) -> dict:
    """Retrieve the AlphaFold DB model for one UniProt accession.

    Returns the record described in `_record`. Raises `NoModelAvailable`,
    `AlphaFoldUnavailable` or `MalformedPrediction` -- never a placeholder.

    With `use_cache` (the default) a second call for the same accession makes
    no network request at all, which is what makes this usable from a Streamlit
    rerun and from an M4 screen over 188 homologs.

    The cache pins the model version recorded at fetch time. AlphaFold DB does
    re-release entries -- C5B164 is on v6, created 2025-08-01, with v2-v5 still
    listed -- so a long-lived cache can be behind the database. `use_cache=False`
    re-fetches. There is no expiry: a silent background refresh would change a
    published number under a reader with no record of why.
    """
    code = valid_accession(accession)
    root, meta_path = _cache_paths(code, cache_dir)
    if use_cache:
        hit = cached_model(code, cache_dir=cache_dir)
        if hit is not None:
            return hit

    metadata = prediction_metadata(code, timeout=timeout)
    url, suffix = _model_url(metadata)
    try:
        response = requests.get(url, timeout=timeout,
                                headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AlphaFoldUnavailable(
            f"AlphaFold DB listed a model for {code} at {url} but it could not "
            f"be downloaded ({type(exc).__name__}).") from exc

    text = response.text
    # Same guard as structure.fetch_structure: a 200 carrying an error page is
    # not coordinates, and an empty model would otherwise parse to zero
    # residues and a confidently wrong mean.
    if "ATOM  " not in text and "_atom_site." not in text:
        raise MalformedPrediction(
            f"Downloaded {url} for {code} but it contains no coordinate records.")

    filename = f"{metadata['entryId']}-model_v{metadata['latestVersion']}.{suffix}"
    root.mkdir(parents=True, exist_ok=True)
    model_file = root / filename
    model_file.write_text(text)

    # Metadata last, and only after the record validates: a crash between the
    # two leaves a stray coordinate file (harmless, overwritten next time)
    # rather than a metadata entry promising a file that is not there.
    record = _record(metadata, model_file)
    meta_path.write_text(json.dumps({**metadata, "_lantern_model_file": filename},
                                    indent=1, sort_keys=True))
    return record


def confidence_gate(plddt_values, *, minimum: float = GATE_MINIMUM_PLDDT,
                    region: str = "region") -> dict:
    """Decide whether a region of a predicted model may be scored at all.

    ROADMAP M4: "Gate on local pLDDT: a low-confidence region yields
    `not_scored`, not a low score." The two verdicts this returns, SCORABLE and
    NOT_SCORED, are that distinction, and nothing here ever returns a number
    standing in for low confidence.

    **The criterion is the worst residue, not the mean.** A lanthanide site is
    four or five donor residues; if one of them sits at pLDDT 40 its side chain
    could be anywhere, so the coordination number counted around it is fiction
    whatever the other four score. Averaging would let four very-high residues
    carry a disordered fifth over the line -- and the mean is exactly the
    statistic that cannot see the single bad donor. The mean is reported for
    context and is explicitly not the test.

    An empty region is NOT_SCORED, not a pass. No residues means no evidence,
    and the fail-closed reading of no evidence is refusal.
    """
    values = [float(v) for v in plddt_values]
    caveats = [
        "pLDDT is AlphaFold's own confidence in its prediction. It is not an "
        "experimental measurement and not a probability that a site exists.",
        "Clearing this gate makes a region eligible to be scored. It does not "
        "make the model correct, and an apo prediction is not the metal-bound "
        "conformation (ROADMAP risk register).",
    ]
    if not values:
        return {
            "verdict": NOT_SCORED,
            "scorable": False,
            "reason": (f"No pLDDT values for this {region}: confidence is unknown, "
                       "so nothing is scored. This is not a low score."),
            "minimum_plddt": minimum,
            "n_residues": 0,
            "mean_plddt": None,
            "min_plddt": None,
            "worst_band": None,
            "residues_below_minimum": 0,
            "side_chains_reliable": False,
            "caveats": caveats,
        }

    worst = min(values)
    mean = sum(values) / len(values)
    below = sum(1 for v in values if v < minimum)
    scorable = below == 0
    side_chains_reliable = worst >= SIDECHAIN_RELIABLE_PLDDT
    if not side_chains_reliable:
        caveats.append(
            f"Lowest pLDDT in this {region} is {worst:.1f}; EBI reserves reliable "
            f"side-chain placement for pLDDT > {SIDECHAIN_RELIABLE_PLDDT:.0f}. "
            "Donor-atom distances and carboxylate denticity read off this model "
            "are backbone-level at best.")

    if scorable:
        reason = (f"Every one of {len(values)} residues in this {region} reaches "
                  f"pLDDT {minimum:.0f} (lowest {worst:.1f}, mean {mean:.1f}).")
    else:
        reason = (f"{below} of {len(values)} residues in this {region} fall below "
                  f"pLDDT {minimum:.0f} (lowest {worst:.1f}, band "
                  f"'{confidence_band(worst)}'). The geometry here is not legible, "
                  f"so it is {NOT_SCORED} -- which is not the same as scored low, "
                  f"and the mean of {mean:.1f} must not be reported as if it were.")

    return {
        "verdict": SCORABLE if scorable else NOT_SCORED,
        "scorable": scorable,
        "reason": reason,
        "minimum_plddt": minimum,
        "n_residues": len(values),
        "mean_plddt": round(mean, 2),
        "min_plddt": round(worst, 2),
        "worst_band": confidence_band(worst),
        "residues_below_minimum": below,
        "side_chains_reliable": side_chains_reliable,
        "caveats": caveats,
    }


def site_confidence(model_file: Path | str, residue_numbers,
                    *, minimum: float = GATE_MINIMUM_PLDDT) -> dict:
    """Gate the specific residues that form a putative site in a cached model.

    "Local pLDDT" in ROADMAP M4 means the residues of the site, not the chain:
    a 133-residue LanM homolog can average 83 and still hold its fourth EF-hand
    in a disordered stretch. Pass the donor residue numbers.

    A residue number absent from the model raises rather than being skipped.
    Skipping would shrink the region to the residues that happen to be
    confident, which is the most flattering possible gate and the exact
    opposite of what it is for. The raised dict names the missing numbers so
    the caller can tell an off-by-one numbering mismatch from a real gap.
    """
    scores = residue_plddt(model_file)
    wanted = [int(n) for n in residue_numbers]
    missing = [n for n in wanted if n not in scores]
    if missing:
        raise MalformedPrediction(
            f"{Path(model_file).name} has no residues {missing}; the model "
            f"covers {min(scores)}-{max(scores)}. Refusing to gate on a subset.")
    gate = confidence_gate([scores[n] for n in wanted], minimum=minimum, region="site")
    gate["residues"] = {n: round(scores[n], 2) for n in wanted}
    return gate


def withhold_if_unconfident(gate: dict, score: dict) -> dict:
    """Return `score` when the gate passed; otherwise a `not_scored` record.

    One place where the M4 rule is enforced, so no caller has to remember it.
    The withheld form carries `score=None` and `call=NOT_SCORED` -- never 0,
    never the score that would have been computed -- plus the gate's reason, so
    a reader of the output can see the candidate was skipped for confidence
    rather than ranked low on merit.

    **Both paths are stamped `evidence` and `experimental`.** The pass path
    used to return `{**score, "confidence": gate}` and nothing else, so the
    only record that carried the "this came from a prediction" label was the
    *withheld* one -- the label was on the result nobody acts on and missing
    from the result that gets ranked, charted and handed to the narrator. The
    risk was exactly inverted. A caller's `score` may legitimately carry its
    own evidence string (a structure-derived score passed through a gate), so
    an existing value is left alone rather than overwritten.
    """
    if gate.get("scorable"):
        passed = {**score, "confidence": gate}
        passed.setdefault("evidence", EVIDENCE)
        passed.setdefault("experimental", False)
        return passed
    return {
        "call": NOT_SCORED,
        "score": None,
        "score_withheld": True,
        "reason": gate.get("reason", "Confidence gate not passed."),
        "confidence": gate,
        "evidence": EVIDENCE,
        "experimental": False,
    }
