# LANTERN | Hackathon Story and Speaker Talking Points

**Central thesis:** Nature provides molecular machinery. Chemistry provides understanding. AI connects them to critical-materials recovery.

**Narrative rule:** Sell the scientific problem and the new connection first. Present the software as evidence that this approach is actionable. Separate what is demonstrated from what remains a hypothesis.

## Slide 1 — Nature knows how to handle metals
- Start with a provocative question: What if some of the chemistry we need for tomorrow's materials is already encoded in biology?
- Nature has spent billions of years evolving molecular recognition.
- Our opportunity is to connect this knowledge to an urgent industrial challenge.
- **Transition:** First, look at what biology already does.

## Slide 2 — Biological intelligence
- Hemoglobin uses an iron-containing heme group to support oxygen transport.
- Copper proteins support electron transfer; zinc is central to many enzymes.
- Biology recognizes, binds, transports, stores, and releases metal ions under controlled conditions.
- This is an established scientific foundation, not a speculative premise.
- **Transition:** Now compare that sophistication with our demand for critical materials.

## Slide 3 — Materials that power the future
- Neodymium is important in high-performance permanent magnets for motors and wind turbines.
- Erbium supports fiber-optic amplifiers; europium is used in phosphors; gadolinium has medical imaging applications.
- Recovery and separation can require intensive chemical and industrial processing.
- Emphasize that demand and supply-chain resilience motivate alternative approaches.
- **Transition:** The hardest challenge is often not finding metals, but separating them.

## Slide 4 — The selectivity problem
- Many rare-earth elements exhibit similar aqueous chemistry, often dominated by the +3 oxidation state.
- A binder that captures every metal equally is not automatically a useful separation material.
- Affinity and selectivity are distinct. Practical recovery also requires release, stability, and reusability.
- **Key line:** We want biological systems that recognize the *right* metal.

## Slide 5 — Two scientific worlds
- Biology offers vast protein sequence and structure resources, including known metal-binding motifs.
- Chemistry offers rules for coordination environments, donor atoms, geometry, competing ions, and solution conditions.
- AI is valuable when it connects evidence that is scattered across disciplines and data sources.
- **Key line:** The opportunity is in the connection, not in pretending either field is new.

## Slide 6 — Introducing LANTERN
- LANTERN is an AI-guided framework for discovering and evaluating metal-binding biological systems.
- Discovery: retrieve candidate proteins and relevant evidence.
- Interpretation: inspect binding sites and chemical plausibility.
- Prioritization: generate ranked hypotheses, with supporting rationale and uncertainty.
- Validation: propose concrete experimental tests.
- **Placeholder:** Add an actual LANTERN screenshot and label which stages currently run.

## Slide 7 — One question, one workflow
- Example question: Which proteins might preferentially bind neodymium over calcium under specified conditions?
- Explain the input: metal target, competitor, environment, and evidence sources.
- Explain the output: candidates, rationale, uncertainty, and next experiments.
- **Important:** This is an illustrative prompt unless the prototype has actually run it.
- **Placeholder:** Replace with a real end-to-end demonstration from the repository.

## Slide 8 — Evidence makes the story credible
- Present one result judges can inspect rather than a collage of promises.
- Show what data were retrieved, how AI contributed, and what the output says.
- A known binder recovered as a benchmark is useful. A new candidate is interesting but requires independent validation.
- Never equate a plausible structural pocket or model score with measured binding affinity.
- **Placeholder:** Insert ranked candidates, structural figure, screenshots, metrics, or a live demo.

## Slide 9 — Why AI, specifically?
- A conventional database query can retrieve a sequence. The higher-value goal is to integrate sequences, structures, papers, and metal chemistry.
- AI can help reason across evidence, expose tradeoffs, and generate testable hypotheses.
- Keep humans and experimental evidence in the loop.
- **Judge question:** What does LANTERN do that a literature search and ordinary bioinformatics script cannot?
- **Answer only with implemented and demonstrable features.**

## Slide 10 — An expandable scientific search space
- Public protein resources contain enormous numbers of sequences, but only a fraction are characterized for a particular metal.
- The design space includes multiple metals, oxidation states, competitor ions, pH, salinity, and protein variants.
- The opportunity is to prioritize this space intelligently rather than screen every combination experimentally.
- The slide's infinity symbol is conceptual, not a literal count.
- **Key line:** Scale creates opportunity. Scientific validation creates trust.

## Slide 11 — Potential impact
- Biological capture may enable selective, aqueous, potentially regenerable processes.
- Initial opportunities may be in recycling, secondary feedstocks, or process streams rather than replacing all mining.
- Avoid claiming proteins are inherently cheaper, fully biodegradable in every application, or guaranteed to reduce lifecycle emissions.
- Those outcomes require technoeconomic analysis, lifecycle assessment, and demonstration at scale.
- **Key line:** We are exploring a complementary route to cleaner recovery, not claiming to have replaced industrial processing.

## Slide 12 — Roadmap
- **Now:** Demonstrate evidence-grounded protein discovery and interpretable candidate ranking.
- **Next:** Benchmark candidates and test affinity, selectivity, capture/release, and robustness experimentally.
- **Later:** Engineer improved binders, integrate reusable capture media, and assess process economics.
- **Placeholder:** Add team expertise, specific milestones, and partnerships.

## Slide 13 — The closing
- Nature provides molecular machinery.
- Chemistry provides understanding.
- AI brings them together.
- **Final line:** We are not asking AI to invent chemistry from nothing. We are asking it to connect the chemistry nature already knows with the materials challenges humanity needs to solve.
- Pause after the last line.

## Slide 14 — Discussion
- Invite feedback on protein candidates, coordination chemistry, experimental validation, and practical recovery use cases.
- **Placeholder:** Add GitHub URL, QR code, team, acknowledgments, and contact details.

---

## Suggested timing (8-minute version)
- Slides 1–2: 1 minute. Establish the biological premise.
- Slides 3–4: 1 minute. Make the materials challenge urgent and specific.
- Slides 5–6: 1.5 minutes. Reveal the AI connection and platform.
- Slides 7–9: 2.5 minutes. Demonstrate the working science and AI contribution.
- Slides 10–12: 1.5 minutes. Show scale, impact, and roadmap.
- Slides 13–14: 0.5 minute. Close and invite questions.

## Likely judge questions and disciplined answers

**Is biological rare-earth binding new?** No. Lanthanide-binding proteins and biological separations are active research areas. LANTERN's proposed contribution is a generalizable, AI-guided workflow for connecting biological candidates with metal chemistry and prioritizing testable hypotheses.

**What is novel about the AI?** Point to implemented cross-source reasoning, chemical interpretation, reproducible ranking, or agent orchestration. Do not claim capabilities that are only planned.

**Have you demonstrated selectivity?** Distinguish predictions and structural hypotheses from direct experimental measurements. If no wet-lab data exist, say so.

**Why is this greener or cheaper?** Potential for mild aqueous processing and reusable capture materials, but the full environmental and economic benefit remains to be established.

**What is the first realistic application?** A constrained recovery stream or recycled feedstock with known metal composition and measurable separation requirements.

## Presenter checklist
- [ ] Add an authentic LANTERN application screenshot.
- [ ] Insert one traceable scientific result and supporting evidence.
- [ ] Clarify which workflow stages are implemented versus planned.
- [ ] Include the team, GitHub link, and demo access.
- [ ] Verify any quantitative performance or environmental claims.
- [ ] Practice the pitch with a strict time limit.

## Scientific anchors to cite in final presentation
- Cotruvo and colleagues' research on lanmodulin and selective lanthanide binding.
- Studies on lanmodulin-based rare-earth separation and lanmodulin ortholog diversity.
- USGS Mineral Commodity Summaries for rare-earth uses and supply-chain context.
- Primary literature for the exact protein candidate or binding-site analysis shown in the live demo.

**Note:** Add full verified references and image credits before public distribution. The current deck prioritizes narrative structure and editable design.
