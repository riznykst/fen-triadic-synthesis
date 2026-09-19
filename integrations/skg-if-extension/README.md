# `ext-cvkg` — draft SKG-IF extension package (NOT submitted)

> **Staging copy inside the FEN repository.** The final home of this package is a
> dedicated `ext-<acronym>` repository under <https://github.com/skg-if>, created
> from the official template once the extension is accepted by the RDA WG on
> SKG-IF. The folder and versioning rules below are theirs, not ours.

Status: **local draft, 2026-09-18.** Nothing here has been submitted, accepted or
published. The extension acronym is provisional and the `w3id.org` URLs below
**do not resolve** until the extension is accepted by the RDA WG on SKG-IF.

Prepared by mapping this repository's working namespace `gfen:`
(`https://w3id.org/got/fen/ontology#`) onto a proper SKG-IF extension.

---

## 1. Verified facts this package is built on (all primary sources)

| Fact | Source |
|---|---|
| SKG-IF Ontology (SKG-O) base IRI: **`https://w3id.org/skg-if/ontology/`**, composed of six modules — agent, data-source, grant, research-product, topic, venue | <https://skg-if.github.io/data-model/> |
| Core entities: Agent · Data source · Grant · **Research product** (literature / data / software / other) · Topic · Venue | same |
| SHACL validation document: **`https://w3id.org/skg-if/validation/shacl`**; data align via the **SKG-IF JSON-LD context** (`https://w3id.org/skg-if/context/`) | same |
| Extension repository layout (binding parts): `data-model/ontology/<X.Y.Z>/` + `current/` (file `<acronym>.ttl`), `data-model/shacl/<X.Y.Z>/` + `current/` (`shacl.ttl`), `context/ver/<X.Y.Z>/` + `current/` (`skg-if.json`), plus `interoperability-framework/`, `api/`, `examples/` | <https://skg-if.github.io/ext-tmpl/structure.html> |
| Permanent URL patterns: ontology `https://w3id.org/skg-if/extension/<acronym>/ontology/[<X.Y.Z>/]`; SHACL `…/validation/shacl/[<X.Y.Z>/]`; context `…/context/[<X.Y.Z>/]skg-if.json` | same |
| Scope allowed: *core-entity extensions* (new properties/relations/controlled values) or *brand-new entities*; API extensions permitted | <https://skg-if.github.io/extensions/> |
| Participation rules: **Shared Interest/Need** (collective, not individual) and **Non-Interference** (must not disrupt existing entities/APIs or duplicate what belongs elsewhere) | same |
| GRAPHIA D2.1: GRAPHIA Ontology = SKG-O + extensions + mappings (SSSOM); each node keeps its own provenance/quality/governance; **extension-level governance rules are not yet defined** | D2.1 (`records/17951755`) pp. 18, 21–22, 26 |

## 2. What this extension claims (scope statement, for the "Shared Interest" test)

> Communities contributing **AI-mediated knowledge** (entities extracted from
> full text, enriched metadata) to a federated knowledge graph currently have no
> shared, machine-readable way to state **how a contribution was validated** —
> by a community vote, by expert review, or by an automated pipeline — nor how to
> record **contestation and rejection**. This extension adds one entity and one
> relation for that purpose.

It is deliberately *not* about: provenance of documents (SKG-O/PROV-O already
cover it), access rights (Data Contracts / ODRL), or federation-level conflict
resolution (GRAPHIA Governance Rules).

## 3. Package layout (mirrors the official template)

```
ext-cvkg/
├── README.md                         ← this file
├── data-model/
│   ├── ontology/1.0.0/cvkg.ttl       ← extension ontology (draft)
│   └── shacl/1.0.0/shacl.ttl         ← SHACL shapes (draft)
├── context/ver/1.0.0/skg-if.json     ← JSON-LD context (draft)
├── examples/
│   └── validation-record.example.jsonld  ← three worked records (validated, automated, disputed)
└── mappings/fen-to-cvkg.sssom.tsv    ← SSSOM mapping from our working namespace
```

Verified locally (2026-09-18): the ontology parses (rdflib, 108 triples); the
SHACL document parses and self-validates (pyshacl, 84 triples, `conforms: True`);
the JSON-LD context parses; the SSSOM file has 8 columns × 7 mappings and no
ragged rows; **the example records conform to the staged SHACL shapes**
(pyshacl `conforms: True`). Nothing here is submitted.

Not yet present (required before submission): `current/` copies, the
`interoperability-framework/` documentation pages and the `api/` extension notes.

## 4. Non-Interference check (self-assessment, to be completed before submitting)

| Question | Answer today |
|---|---|
| Does it add properties to core entities rather than overloading them? | Yes — one new object property, `cvkg:hasValidationAssertion`, plus one new entity |
| Does it duplicate an existing SKG-O/PROV-O mechanism? | No — SKG-O carries descriptive metadata; PROV-O carries activity provenance; neither carries a *validation verdict with method and dispute state* |
| Does it require changing the core data model or API? | No — additive; an API extension is optional and documented separately |
| Is the interest collective or individual? | **Open question** — needs a co-proponent or a documented community need (e.g. heritage-science or low-resource-language communities) |
| Are simulated values marked as such? | Yes — the anchor field documents `0xMOCK` and `simulated: true` |

## 5. Submission path (when the community question is answered)

1. Open an issue in <https://github.com/skg-if/extensions> using the
   `new-skg-if-extension.md` template (all fields mandatory).
2. Address RDA WG review comments; the acronym and scope may change there.
3. On acceptance, a repository `ext-<acronym>` is created from
   <https://github.com/skg-if/ext-tmpl>; move this package into it, add the
   `current/` copies, and push — a GitHub Action publishes the minisite.
4. Only then do the `w3id.org/skg-if/extension/<acronym>/…` URLs resolve, and
   only then should `gfen:` be replaced by the extension IRI in the FEN
   ontology/README.
