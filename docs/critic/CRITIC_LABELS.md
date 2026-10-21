# Critic hand labels

Questions: `proteins for capturing Ce3+`  
Claims: 12

Put one of `supports` / `contradicts` / `no_evidence` after `label:` on each `##` line.
Leave it blank to skip that claim. Judge its agreement with **the passages printed
underneath it** -- that is all the judge is shown, so a claim the literature answers
elsewhere is still `no_evidence` here. Then:

```
python scripts/critic_label.py score --labels docs/critic/CRITIC_LABELS.md --runs 5 --provider argo
```

---

## q1:c1  label:

CLAIM
  Dy3+ in lanmodulin EF-hand sites has coordination number 9 (O/N/S donors within 3.2 A), measured at 9 such sites in 8FNR

EVIDENCE -- 4 passage(s), exactly as the judge sees them
  [1] 10.26434/chemrxiv-2025-q7jl8 | 2025 | chemrxiv | BM25 10.7 | preprint
      Peptide Charge Modulates Ion Binding to EF-Hand Motifs: A Molecular Dynamics Study

      Rare earth elements (REEs), particularly lanthanides (Ln), are of significant interest due to their
      critical roles in modern technology and medicine. However, their extraction, isolation, and purification
      remain challenging. Lanmodulin (LanM), a recently discovered EF-hand protein, exhibits high affinity and
      selectivity for binding Ln3+ ions. This enhanced affinity is partly attributed to the presence of
      additional acidic residues within its EF-hand metal binding loops. Previous studies have demonstrated
      that reducing the number of ligating acidic residues within EF-hand motifs significantly decreases their
      binding affinities for La3+. Yet, the underlying molecular mechanisms remain poorly understood. To
      address this, we performed molecular dynamics (MD) simulations and MMPBSA/MMGBSA analyses on a series of
      EF-hand motifs with varying numbers of ligating acidic residues. Our results reveal that the number of
      acidic ligands strongly influences the structure of the peptide–ion complex. Specifically, a decrease in
      ligating acidic residue leads to increased coordination of water molecules to La3+. We also observed a
      complex interplay among different ligand types, including ligating acidic and neutral residues,
      non-ligating acidic residues, backbone carbonyls, and water molecules. Notably, reducing the number of
      acidic ligands significantly alters the secondary structure of the EF-hand motif, increases its
      flexibility, and reshapes its free energy landscape. This study provides important molecular insights
      into how peptide charge modulates ion binding to EF-hand motifs, offering valuable guidance for the
      rational design of EF-hand proteins with tailored ion-binding properties.

  [2] 10.26434/chemrxiv.15005421/v1 | 2026 | chemrxiv | BM25 9.0 | preprint
      Quantum-Guided Binding-Site Engineering of Lanmodulin for Zero-Waste Separation of Critical Rare-Earth Elements

      Rare-earth separation remains energy-intensive and waste-generating, motivating aqueous alternatives for
      selective lanthanide capture. We report a deterministic computational workflow that couples binding-site
      engineering of lanmodulin with multireference quantum characterization toward dysprosium prioritization.
      Four experimentally solved lanmodulin structures were harmonized, residue roles were assigned to
      preserve the first-shell coordination environment while allowing selected second-sphere and interface
      positions to mutate, and ProteinMPNN, LigandMPNN, Rosetta triage, and reduced OpenMM rescreening were
      used to rank redesigned pockets against dysprosium, neodymium, yttrium, aluminum, and iron. The workflow
      reduced 66 evaluated mask positions to 3 finalists while retaining rare-earth binding in all cases. The
      top-ranked Hans-derived pocket showed the strongest local confidence signal, the lowest pocket
      free-energy proxy, and stable rare-earth coordination, but aluminum and iron capture persisted across
      all three candidate pockets. The nominated pocket was then advanced to multiconfigurational treatment:
      compact Dy(III) and Nd(III) coordination clusters were extracted and characterized with CASSCF and
      CASPT2 using a 4f active space, confirming a physically valid 4f manifold for each metal and a
      well-converged multireference description. These results deliver a quantum-characterized
      dysprosium-prioritized lanmodulin pocket and matched Dy/Nd electronic-structure references, and show
      that competitor suppression remains the main design challenge.

  [3] 10.1096/fasebj.2022.36.s1.r4572 | 2022 | crossref | BM25 8.7
      Investigating Landmodulin's EF Hands in Relation to Lanthanide Recycling Methods

      Rare earth elements (REEs) have distinct and varied electronic properties that have been applied for
      military and civilian use in electronics, such as cell phones and computer chip technologies. The
      recycling methods for REEs are complex and require a multitude of resources that prompt new studies to
      improve REEs separations. Lanmodulin (LanM), a protein that naturally bind to lanthanides, may provide a
      biological route for REE separation. Understanding the structure of LanM’s EF‐hands will explain how the
      lanthanides bond to them and lead to a greater understanding of how LanM can be used to recycle REEs to
      benefit our environment. The Summit Country Day School MSOE Center for BioMolecular Modeling MAPS Team
      used 3D modeling and printing technology to examine structure‐function relationships of EF1‐3 hands on
      lanmodulin. LanM has three tight binding EF‐hands, EF1 (D35‐E46), EF2 (D59‐E70), and EF3 (D84‐ E95),
      which are abundant in carboxylate side chains that bind the lanthanides. Lanthanide binding promotes a
      large conformational shift of the protein from a disorganized state to an organized state. The interior
      of the protein is a condensed helical bundle, and the majority of the exterior is composed of the EF
      hands, making bonding with lanthanides easier due to the EF hands being solely on the exterior. These
      three hands contain a higher number of coordination numbers (8‐9) compared to only 7 in Calmodulin
      (CaM), resulting in more specialized bonding properties. LanM also has a conserved proline between the
      first and second putative metal‐coordinating residues in each of the four EF hands, which is unique to
      this protein and may play a role in reducing affinity for calcium ions. In conclusion, analyzing the
      properties of the binding sites of EF1‐3 in LanM through 3D modeling can reveal insights on utilizing
      proteins as a method to extract and recycle REE in order to be environmentally cognizant.

  [4] 10.26434/chemrxiv.15009104/v1 | 2026 | chemrxiv | BM25 8.5 | preprint
      Water Layering and Orientation Modulate Lanthanide Hydration in Carbon Nanotubes

      Nanoscale confinement can reorganize water molecules and alter ionic hydration, offering a potential
      route to separating chemically similar ions. We use molecular dynamics simulations with the MACE-MH-1
      foundation machine-learning interatomic potential to investigate the hydration of eight trivalent
      lanthanide ions (Ln 3+ : La 3+ , Pr 3+ , Nd 3+ , Gd 3+ , Tb 3+ , Dy 3+ , Tm 3+ , and Lu 3+ ) in carbon
      nanotubes (CNTs) with diameters of 1.09–1.49 nm. We first evaluate MACE-MH-1 for Ln 3+ hydration in bulk
      solution. The OMOL model of MACE-MH-1 reproduces the reported Ln–O distances and coordination-number
      trends and is therefore used for the CNT simulations. The hydration factor, which measures first-shell
      orientational order, varies nonmonotonically with CNT diameter and reaches a minimum in CNT(9,9), which
      also accommodates the most first-shell water molecules. This minimum coincides with the emergence of a
      central water population and reflects two combined effects: difference in preferred orientation between
      first-shell and surrounding water molecules and increased hydrogen-bond coupling between them. However,
      different Ln 3+ ions respond similarly to confinement, suggesting that CNT confinement alone may offer
      limited selectivity for their separation.

---

## q1:c2  label:

CLAIM
  Dy3+ in lanmodulin EF-hand sites has coordination number 7 (O/N/S donors within 3.2 A), measured at 4 such sites in 8FNR

EVIDENCE -- 4 passage(s), exactly as the judge sees them
  [5] 10.26434/chemrxiv-2025-q7jl8 | 2025 | chemrxiv | BM25 10.7 | preprint
      Peptide Charge Modulates Ion Binding to EF-Hand Motifs: A Molecular Dynamics Study

      Rare earth elements (REEs), particularly lanthanides (Ln), are of significant interest due to their
      critical roles in modern technology and medicine. However, their extraction, isolation, and purification
      remain challenging. Lanmodulin (LanM), a recently discovered EF-hand protein, exhibits high affinity and
      selectivity for binding Ln3+ ions. This enhanced affinity is partly attributed to the presence of
      additional acidic residues within its EF-hand metal binding loops. Previous studies have demonstrated
      that reducing the number of ligating acidic residues within EF-hand motifs significantly decreases their
      binding affinities for La3+. Yet, the underlying molecular mechanisms remain poorly understood. To
      address this, we performed molecular dynamics (MD) simulations and MMPBSA/MMGBSA analyses on a series of
      EF-hand motifs with varying numbers of ligating acidic residues. Our results reveal that the number of
      acidic ligands strongly influences the structure of the peptide–ion complex. Specifically, a decrease in
      ligating acidic residue leads to increased coordination of water molecules to La3+. We also observed a
      complex interplay among different ligand types, including ligating acidic and neutral residues,
      non-ligating acidic residues, backbone carbonyls, and water molecules. Notably, reducing the number of
      acidic ligands significantly alters the secondary structure of the EF-hand motif, increases its
      flexibility, and reshapes its free energy landscape. This study provides important molecular insights
      into how peptide charge modulates ion binding to EF-hand motifs, offering valuable guidance for the
      rational design of EF-hand proteins with tailored ion-binding properties.

  [6] 10.26434/chemrxiv.15005421/v1 | 2026 | chemrxiv | BM25 9.0 | preprint
      Quantum-Guided Binding-Site Engineering of Lanmodulin for Zero-Waste Separation of Critical Rare-Earth Elements

      Rare-earth separation remains energy-intensive and waste-generating, motivating aqueous alternatives for
      selective lanthanide capture. We report a deterministic computational workflow that couples binding-site
      engineering of lanmodulin with multireference quantum characterization toward dysprosium prioritization.
      Four experimentally solved lanmodulin structures were harmonized, residue roles were assigned to
      preserve the first-shell coordination environment while allowing selected second-sphere and interface
      positions to mutate, and ProteinMPNN, LigandMPNN, Rosetta triage, and reduced OpenMM rescreening were
      used to rank redesigned pockets against dysprosium, neodymium, yttrium, aluminum, and iron. The workflow
      reduced 66 evaluated mask positions to 3 finalists while retaining rare-earth binding in all cases. The
      top-ranked Hans-derived pocket showed the strongest local confidence signal, the lowest pocket
      free-energy proxy, and stable rare-earth coordination, but aluminum and iron capture persisted across
      all three candidate pockets. The nominated pocket was then advanced to multiconfigurational treatment:
      compact Dy(III) and Nd(III) coordination clusters were extracted and characterized with CASSCF and
      CASPT2 using a 4f active space, confirming a physically valid 4f manifold for each metal and a
      well-converged multireference description. These results deliver a quantum-characterized
      dysprosium-prioritized lanmodulin pocket and matched Dy/Nd electronic-structure references, and show
      that competitor suppression remains the main design challenge.

  [7] 10.1096/fasebj.2022.36.s1.r4572 | 2022 | crossref | BM25 8.0
      Investigating Landmodulin's EF Hands in Relation to Lanthanide Recycling Methods

      Rare earth elements (REEs) have distinct and varied electronic properties that have been applied for
      military and civilian use in electronics, such as cell phones and computer chip technologies. The
      recycling methods for REEs are complex and require a multitude of resources that prompt new studies to
      improve REEs separations. Lanmodulin (LanM), a protein that naturally bind to lanthanides, may provide a
      biological route for REE separation. Understanding the structure of LanM’s EF‐hands will explain how the
      lanthanides bond to them and lead to a greater understanding of how LanM can be used to recycle REEs to
      benefit our environment. The Summit Country Day School MSOE Center for BioMolecular Modeling MAPS Team
      used 3D modeling and printing technology to examine structure‐function relationships of EF1‐3 hands on
      lanmodulin. LanM has three tight binding EF‐hands, EF1 (D35‐E46), EF2 (D59‐E70), and EF3 (D84‐ E95),
      which are abundant in carboxylate side chains that bind the lanthanides. Lanthanide binding promotes a
      large conformational shift of the protein from a disorganized state to an organized state. The interior
      of the protein is a condensed helical bundle, and the majority of the exterior is composed of the EF
      hands, making bonding with lanthanides easier due to the EF hands being solely on the exterior. These
      three hands contain a higher number of coordination numbers (8‐9) compared to only 7 in Calmodulin
      (CaM), resulting in more specialized bonding properties. LanM also has a conserved proline between the
      first and second putative metal‐coordinating residues in each of the four EF hands, which is unique to
      this protein and may play a role in reducing affinity for calcium ions. In conclusion, analyzing the
      properties of the binding sites of EF1‐3 in LanM through 3D modeling can reveal insights on utilizing
      proteins as a method to extract and recycle REE in order to be environmentally cognizant.

  [8] 10.1002/chem.71438 | 2026 | crossref | BM25 7.5
      Influence of Head‐to‐Tail Cyclization of Lanmodulin‐Inspired Peptides on Lanthanide Affinity and Structure

      ABSTRACT Over the recent years, lanthanide (Ln)‐binding proteins such as lanmodulin, a naturally
      Ln‐binding EF‐hand protein from Methylorubrum extorquens AM1, as well as protein‐inspired short
      Ln‐binding peptides, have become of increasing interest for the development of separation and recycling
      methods for rare earth elements. Here, we comprehensively examined a set of head‐to‐tail cyclized
      lanmodulin‐EF‐hand sequence‐inspired peptides and their complexation behavior toward Lns using
      time‐resolved laser‐induced fluorescence spectroscopy (TRLFS), isothermal titration calorimetry (ITC),
      nuclear magnetic resonance (NMR), and circular dichroism (CD) spectroscopies, complemented by molecular
      dynamic (MD) simulations and advanced mass spectrometry methods. Results obtained from this multi‐method
      approach evidence that the head‐to‐tail cyclization can indeed increase the Ln affinity in some cases
      and positively impact the pre‐organization of the metal‐free peptide while predominantly forming 1:1
      complexes in comparison to linear analogues, which can form both 1:1 and 1:2 species. Furthermore, the
      impact of a sequence alteration by inserting glycine at the head‐to‐tail junction is shown to be useful
      in NMR experiments for probing alterations in the local environment of neighboring amino acids (AA)
      potentially involved in coordination. Lastly, K D values for the peptides with the whole Ln series
      (except Pm) and the actinide curium are presented.

---

## q1:c3  label:

CLAIM
  Dy3+ in lanmodulin EF-hand sites has coordination number 4 (O/N/S donors within 3.2 A), measured at 1 such site in 8FNR

EVIDENCE -- 4 passage(s), exactly as the judge sees them
  [9] 10.26434/chemrxiv-2025-q7jl8 | 2025 | chemrxiv | BM25 10.7 | preprint
      Peptide Charge Modulates Ion Binding to EF-Hand Motifs: A Molecular Dynamics Study

      Rare earth elements (REEs), particularly lanthanides (Ln), are of significant interest due to their
      critical roles in modern technology and medicine. However, their extraction, isolation, and purification
      remain challenging. Lanmodulin (LanM), a recently discovered EF-hand protein, exhibits high affinity and
      selectivity for binding Ln3+ ions. This enhanced affinity is partly attributed to the presence of
      additional acidic residues within its EF-hand metal binding loops. Previous studies have demonstrated
      that reducing the number of ligating acidic residues within EF-hand motifs significantly decreases their
      binding affinities for La3+. Yet, the underlying molecular mechanisms remain poorly understood. To
      address this, we performed molecular dynamics (MD) simulations and MMPBSA/MMGBSA analyses on a series of
      EF-hand motifs with varying numbers of ligating acidic residues. Our results reveal that the number of
      acidic ligands strongly influences the structure of the peptide–ion complex. Specifically, a decrease in
      ligating acidic residue leads to increased coordination of water molecules to La3+. We also observed a
      complex interplay among different ligand types, including ligating acidic and neutral residues,
      non-ligating acidic residues, backbone carbonyls, and water molecules. Notably, reducing the number of
      acidic ligands significantly alters the secondary structure of the EF-hand motif, increases its
      flexibility, and reshapes its free energy landscape. This study provides important molecular insights
      into how peptide charge modulates ion binding to EF-hand motifs, offering valuable guidance for the
      rational design of EF-hand proteins with tailored ion-binding properties.

  [10] 10.26434/chemrxiv.15005421/v1 | 2026 | chemrxiv | BM25 9.0 | preprint
      Quantum-Guided Binding-Site Engineering of Lanmodulin for Zero-Waste Separation of Critical Rare-Earth Elements

      Rare-earth separation remains energy-intensive and waste-generating, motivating aqueous alternatives for
      selective lanthanide capture. We report a deterministic computational workflow that couples binding-site
      engineering of lanmodulin with multireference quantum characterization toward dysprosium prioritization.
      Four experimentally solved lanmodulin structures were harmonized, residue roles were assigned to
      preserve the first-shell coordination environment while allowing selected second-sphere and interface
      positions to mutate, and ProteinMPNN, LigandMPNN, Rosetta triage, and reduced OpenMM rescreening were
      used to rank redesigned pockets against dysprosium, neodymium, yttrium, aluminum, and iron. The workflow
      reduced 66 evaluated mask positions to 3 finalists while retaining rare-earth binding in all cases. The
      top-ranked Hans-derived pocket showed the strongest local confidence signal, the lowest pocket
      free-energy proxy, and stable rare-earth coordination, but aluminum and iron capture persisted across
      all three candidate pockets. The nominated pocket was then advanced to multiconfigurational treatment:
      compact Dy(III) and Nd(III) coordination clusters were extracted and characterized with CASSCF and
      CASPT2 using a 4f active space, confirming a physically valid 4f manifold for each metal and a
      well-converged multireference description. These results deliver a quantum-characterized
      dysprosium-prioritized lanmodulin pocket and matched Dy/Nd electronic-structure references, and show
      that competitor suppression remains the main design challenge.

  [11] 10.1002/chem.71438 | 2026 | crossref | BM25 7.5
      Influence of Head‐to‐Tail Cyclization of Lanmodulin‐Inspired Peptides on Lanthanide Affinity and Structure

      ABSTRACT Over the recent years, lanthanide (Ln)‐binding proteins such as lanmodulin, a naturally
      Ln‐binding EF‐hand protein from Methylorubrum extorquens AM1, as well as protein‐inspired short
      Ln‐binding peptides, have become of increasing interest for the development of separation and recycling
      methods for rare earth elements. Here, we comprehensively examined a set of head‐to‐tail cyclized
      lanmodulin‐EF‐hand sequence‐inspired peptides and their complexation behavior toward Lns using
      time‐resolved laser‐induced fluorescence spectroscopy (TRLFS), isothermal titration calorimetry (ITC),
      nuclear magnetic resonance (NMR), and circular dichroism (CD) spectroscopies, complemented by molecular
      dynamic (MD) simulations and advanced mass spectrometry methods. Results obtained from this multi‐method
      approach evidence that the head‐to‐tail cyclization can indeed increase the Ln affinity in some cases
      and positively impact the pre‐organization of the metal‐free peptide while predominantly forming 1:1
      complexes in comparison to linear analogues, which can form both 1:1 and 1:2 species. Furthermore, the
      impact of a sequence alteration by inserting glycine at the head‐to‐tail junction is shown to be useful
      in NMR experiments for probing alterations in the local environment of neighboring amino acids (AA)
      potentially involved in coordination. Lastly, K D values for the peptides with the whole Ln series
      (except Pm) and the actinide curium are presented.

  [12] 10.26434/chemrxiv-2021-36s56 | 2021 | chemrxiv | BM25 6.7 | preprint
      LanM Peptides – Unravelling the Binding Properties of the EF-Hand Loop Sequences Stripped from the Structural Corset

      Since the discovery of the biological relevance of lanthanides (Lns) for methylotrophic bacteria in the
      last decade, the field has seen a steady rise in discoveries of bacteria using Lns. The major role of
      lanthanides here is in the active sites of enzymes: methanol dehydrogenases. Additionally, lanthanide
      binding proteins have also been identified. One such protein is lanmodulin (LanM) and, with a remarkable
      selectivity for Lns over Ca(II) and affinities in the picomolar range, it makes an attractive target to
      address challenges in lanthanide separation. Why LanM has such a high selectivity is currently not
      entirely understood, both the specific amino acid sequences of the EF-hand loops, together with
      cooperativity effects have been suggested. Consequently, we decided to remove the effect of
      cooperativity by focusing on the amino acid level. Thus, we synthesized all four 12-amino acid EF-Hand
      loop peptides of LanM using solid phase peptide synthesis and investigated their affinity for Lns
      (Eu(III), Tb(III)), the actinide Cm(III) and Ca(II). Using isothermal titration calorimetry and time
      resolved laser fluorescence spectroscopy combined with parallel factor analysis, we show that in the
      absence of cooperativity the short EF-Hand loop peptides have all similar affinities for lanthanides and
      that these are all in the micromolar range. Furthermore, calcium was shown not to bind to the peptides
      which was verified with circular dichroism spectroscopy. This technique also revealed that the peptides
      undergo a change to a more ordered state when lanthanides are added. These experimental observations
      were further supported by molecular dynamics simulations. Lastly, we put Eu(III) and Cm(III) in direct
      competition using TRLFS. Remarkably, a slightly higher affinity for the actinide, as was also observed
      for LanM, was found. Our results demonstrate that the picomolar affinities in LanM are largely an effect
      of pre-structuring in the full protein and therefore reduction of flexibility in combination with
      cooperative effects, and that all EF-Hand loops possess similar affinities when detached from the
      protein backbone, albeit still retaining the high selectivity for lanthanides and actinides over
      calcium.

---

## q1:c4  label:

CLAIM
  Nd3+ in lanmodulin EF-hand sites has coordination number 9 (O/N/S donors within 3.2 A), measured at 3 such sites in 8FNS

EVIDENCE -- 4 passage(s), exactly as the judge sees them
  [13] 10.26434/chemrxiv-2025-q7jl8 | 2025 | chemrxiv | BM25 10.7 | preprint
      Peptide Charge Modulates Ion Binding to EF-Hand Motifs: A Molecular Dynamics Study

      Rare earth elements (REEs), particularly lanthanides (Ln), are of significant interest due to their
      critical roles in modern technology and medicine. However, their extraction, isolation, and purification
      remain challenging. Lanmodulin (LanM), a recently discovered EF-hand protein, exhibits high affinity and
      selectivity for binding Ln3+ ions. This enhanced affinity is partly attributed to the presence of
      additional acidic residues within its EF-hand metal binding loops. Previous studies have demonstrated
      that reducing the number of ligating acidic residues within EF-hand motifs significantly decreases their
      binding affinities for La3+. Yet, the underlying molecular mechanisms remain poorly understood. To
      address this, we performed molecular dynamics (MD) simulations and MMPBSA/MMGBSA analyses on a series of
      EF-hand motifs with varying numbers of ligating acidic residues. Our results reveal that the number of
      acidic ligands strongly influences the structure of the peptide–ion complex. Specifically, a decrease in
      ligating acidic residue leads to increased coordination of water molecules to La3+. We also observed a
      complex interplay among different ligand types, including ligating acidic and neutral residues,
      non-ligating acidic residues, backbone carbonyls, and water molecules. Notably, reducing the number of
      acidic ligands significantly alters the secondary structure of the EF-hand motif, increases its
      flexibility, and reshapes its free energy landscape. This study provides important molecular insights
      into how peptide charge modulates ion binding to EF-hand motifs, offering valuable guidance for the
      rational design of EF-hand proteins with tailored ion-binding properties.

  [14] 10.1096/fasebj.2022.36.s1.r4572 | 2022 | crossref | BM25 8.7
      Investigating Landmodulin's EF Hands in Relation to Lanthanide Recycling Methods

      Rare earth elements (REEs) have distinct and varied electronic properties that have been applied for
      military and civilian use in electronics, such as cell phones and computer chip technologies. The
      recycling methods for REEs are complex and require a multitude of resources that prompt new studies to
      improve REEs separations. Lanmodulin (LanM), a protein that naturally bind to lanthanides, may provide a
      biological route for REE separation. Understanding the structure of LanM’s EF‐hands will explain how the
      lanthanides bond to them and lead to a greater understanding of how LanM can be used to recycle REEs to
      benefit our environment. The Summit Country Day School MSOE Center for BioMolecular Modeling MAPS Team
      used 3D modeling and printing technology to examine structure‐function relationships of EF1‐3 hands on
      lanmodulin. LanM has three tight binding EF‐hands, EF1 (D35‐E46), EF2 (D59‐E70), and EF3 (D84‐ E95),
      which are abundant in carboxylate side chains that bind the lanthanides. Lanthanide binding promotes a
      large conformational shift of the protein from a disorganized state to an organized state. The interior
      of the protein is a condensed helical bundle, and the majority of the exterior is composed of the EF
      hands, making bonding with lanthanides easier due to the EF hands being solely on the exterior. These
      three hands contain a higher number of coordination numbers (8‐9) compared to only 7 in Calmodulin
      (CaM), resulting in more specialized bonding properties. LanM also has a conserved proline between the
      first and second putative metal‐coordinating residues in each of the four EF hands, which is unique to
      this protein and may play a role in reducing affinity for calcium ions. In conclusion, analyzing the
      properties of the binding sites of EF1‐3 in LanM through 3D modeling can reveal insights on utilizing
      proteins as a method to extract and recycle REE in order to be environmentally cognizant.

  [15] 10.26434/chemrxiv.15009104/v1 | 2026 | chemrxiv | BM25 8.6 | preprint
      Water Layering and Orientation Modulate Lanthanide Hydration in Carbon Nanotubes

      Nanoscale confinement can reorganize water molecules and alter ionic hydration, offering a potential
      route to separating chemically similar ions. We use molecular dynamics simulations with the MACE-MH-1
      foundation machine-learning interatomic potential to investigate the hydration of eight trivalent
      lanthanide ions (Ln 3+ : La 3+ , Pr 3+ , Nd 3+ , Gd 3+ , Tb 3+ , Dy 3+ , Tm 3+ , and Lu 3+ ) in carbon
      nanotubes (CNTs) with diameters of 1.09–1.49 nm. We first evaluate MACE-MH-1 for Ln 3+ hydration in bulk
      solution. The OMOL model of MACE-MH-1 reproduces the reported Ln–O distances and coordination-number
      trends and is therefore used for the CNT simulations. The hydration factor, which measures first-shell
      orientational order, varies nonmonotonically with CNT diameter and reaches a minimum in CNT(9,9), which
      also accommodates the most first-shell water molecules. This minimum coincides with the emergence of a
      central water population and reflects two combined effects: difference in preferred orientation between
      first-shell and surrounding water molecules and increased hydrogen-bond coupling between them. However,
      different Ln 3+ ions respond similarly to confinement, suggesting that CNT confinement alone may offer
      limited selectivity for their separation.

  [16] 10.26434/chemrxiv.15005421/v1 | 2026 | chemrxiv | BM25 8.4 | preprint
      Quantum-Guided Binding-Site Engineering of Lanmodulin for Zero-Waste Separation of Critical Rare-Earth Elements

      Rare-earth separation remains energy-intensive and waste-generating, motivating aqueous alternatives for
      selective lanthanide capture. We report a deterministic computational workflow that couples binding-site
      engineering of lanmodulin with multireference quantum characterization toward dysprosium prioritization.
      Four experimentally solved lanmodulin structures were harmonized, residue roles were assigned to
      preserve the first-shell coordination environment while allowing selected second-sphere and interface
      positions to mutate, and ProteinMPNN, LigandMPNN, Rosetta triage, and reduced OpenMM rescreening were
      used to rank redesigned pockets against dysprosium, neodymium, yttrium, aluminum, and iron. The workflow
      reduced 66 evaluated mask positions to 3 finalists while retaining rare-earth binding in all cases. The
      top-ranked Hans-derived pocket showed the strongest local confidence signal, the lowest pocket
      free-energy proxy, and stable rare-earth coordination, but aluminum and iron capture persisted across
      all three candidate pockets. The nominated pocket was then advanced to multiconfigurational treatment:
      compact Dy(III) and Nd(III) coordination clusters were extracted and characterized with CASSCF and
      CASPT2 using a 4f active space, confirming a physically valid 4f manifold for each metal and a
      well-converged multireference description. These results deliver a quantum-characterized
      dysprosium-prioritized lanmodulin pocket and matched Dy/Nd electronic-structure references, and show
      that competitor suppression remains the main design challenge.

---

## q1:c5  label:

CLAIM
  Nd3+ in lanmodulin EF-hand sites has coordination number 10 (O/N/S donors within 3.2 A), measured at 1 such site in 8FNS

EVIDENCE -- 4 passage(s), exactly as the judge sees them
  [17] 10.26434/chemrxiv-2025-q7jl8 | 2025 | chemrxiv | BM25 10.7 | preprint
      Peptide Charge Modulates Ion Binding to EF-Hand Motifs: A Molecular Dynamics Study

      Rare earth elements (REEs), particularly lanthanides (Ln), are of significant interest due to their
      critical roles in modern technology and medicine. However, their extraction, isolation, and purification
      remain challenging. Lanmodulin (LanM), a recently discovered EF-hand protein, exhibits high affinity and
      selectivity for binding Ln3+ ions. This enhanced affinity is partly attributed to the presence of
      additional acidic residues within its EF-hand metal binding loops. Previous studies have demonstrated
      that reducing the number of ligating acidic residues within EF-hand motifs significantly decreases their
      binding affinities for La3+. Yet, the underlying molecular mechanisms remain poorly understood. To
      address this, we performed molecular dynamics (MD) simulations and MMPBSA/MMGBSA analyses on a series of
      EF-hand motifs with varying numbers of ligating acidic residues. Our results reveal that the number of
      acidic ligands strongly influences the structure of the peptide–ion complex. Specifically, a decrease in
      ligating acidic residue leads to increased coordination of water molecules to La3+. We also observed a
      complex interplay among different ligand types, including ligating acidic and neutral residues,
      non-ligating acidic residues, backbone carbonyls, and water molecules. Notably, reducing the number of
      acidic ligands significantly alters the secondary structure of the EF-hand motif, increases its
      flexibility, and reshapes its free energy landscape. This study provides important molecular insights
      into how peptide charge modulates ion binding to EF-hand motifs, offering valuable guidance for the
      rational design of EF-hand proteins with tailored ion-binding properties.

  [18] 10.26434/chemrxiv.15005421/v1 | 2026 | chemrxiv | BM25 8.4 | preprint
      Quantum-Guided Binding-Site Engineering of Lanmodulin for Zero-Waste Separation of Critical Rare-Earth Elements

      Rare-earth separation remains energy-intensive and waste-generating, motivating aqueous alternatives for
      selective lanthanide capture. We report a deterministic computational workflow that couples binding-site
      engineering of lanmodulin with multireference quantum characterization toward dysprosium prioritization.
      Four experimentally solved lanmodulin structures were harmonized, residue roles were assigned to
      preserve the first-shell coordination environment while allowing selected second-sphere and interface
      positions to mutate, and ProteinMPNN, LigandMPNN, Rosetta triage, and reduced OpenMM rescreening were
      used to rank redesigned pockets against dysprosium, neodymium, yttrium, aluminum, and iron. The workflow
      reduced 66 evaluated mask positions to 3 finalists while retaining rare-earth binding in all cases. The
      top-ranked Hans-derived pocket showed the strongest local confidence signal, the lowest pocket
      free-energy proxy, and stable rare-earth coordination, but aluminum and iron capture persisted across
      all three candidate pockets. The nominated pocket was then advanced to multiconfigurational treatment:
      compact Dy(III) and Nd(III) coordination clusters were extracted and characterized with CASSCF and
      CASPT2 using a 4f active space, confirming a physically valid 4f manifold for each metal and a
      well-converged multireference description. These results deliver a quantum-characterized
      dysprosium-prioritized lanmodulin pocket and matched Dy/Nd electronic-structure references, and show
      that competitor suppression remains the main design challenge.

  [19] 10.26434/chemrxiv.6008294.v1 | 2018 | chemrxiv | BM25 8.2 | preprint
      Bright near Infrared Neodymium Emission from Europium Sensitisation in β-Triketonate Coordination Polymers

      Isomorphous β -triketonate-based lanthanoid polymers containing tris(4-methylbenzoyl)methane ( mtbm )
      and RbOH with formula, {[Ln(Rb)( mtbm ) 4 ] 2 } n (Ln = Eu 3+ and Nd 3+ ) have been synthesised and
      structurally characterised. The photophysical properties for the Nd 3+ complex presented long lifetimes
      and relatively high quantum yields in comparison with analogous β -diketonate complexes. Mixed
      lanthanoid complexes were also formed and their luminescence properties studied, with effective
      sensitisation of the 4 F 3/2 of Nd 3+ via the 5 D 0 of Eu 3+ , which is to the best of our knowledge the
      first example of Eu 3+ to Nd 3+ sensitisation in coordination polymers

  [20] 10.1002/chem.71438 | 2026 | crossref | BM25 7.5
      Influence of Head‐to‐Tail Cyclization of Lanmodulin‐Inspired Peptides on Lanthanide Affinity and Structure

      ABSTRACT Over the recent years, lanthanide (Ln)‐binding proteins such as lanmodulin, a naturally
      Ln‐binding EF‐hand protein from Methylorubrum extorquens AM1, as well as protein‐inspired short
      Ln‐binding peptides, have become of increasing interest for the development of separation and recycling
      methods for rare earth elements. Here, we comprehensively examined a set of head‐to‐tail cyclized
      lanmodulin‐EF‐hand sequence‐inspired peptides and their complexation behavior toward Lns using
      time‐resolved laser‐induced fluorescence spectroscopy (TRLFS), isothermal titration calorimetry (ITC),
      nuclear magnetic resonance (NMR), and circular dichroism (CD) spectroscopies, complemented by molecular
      dynamic (MD) simulations and advanced mass spectrometry methods. Results obtained from this multi‐method
      approach evidence that the head‐to‐tail cyclization can indeed increase the Ln affinity in some cases
      and positively impact the pre‐organization of the metal‐free peptide while predominantly forming 1:1
      complexes in comparison to linear analogues, which can form both 1:1 and 1:2 species. Furthermore, the
      impact of a sequence alteration by inserting glycine at the head‐to‐tail junction is shown to be useful
      in NMR experiments for probing alterations in the local environment of neighboring amino acids (AA)
      potentially involved in coordination. Lastly, K D values for the peptides with the whole Ln series
      (except Pm) and the actinide curium are presented.

---

## q1:c6  label:

CLAIM
  Lanthanide-binding proteins of the lanmodulin architecture answer yes to the design rule 'Is it shorter than 200 residues?' (measured 133 in A0A4V2JDD3, 133 in C5B164)

EVIDENCE -- 4 passage(s), exactly as the judge sees them
  [21] 10.1002/ejic.202500258 | 2025 | crossref | BM25 6.0
      Lanthanide‐Binding Lanmodulin‐Based Peptides: Insights from Advanced Mass Spectrometry Techniques

      Selective peptide ligands for lanthanides (Ln) have multiple applications in, for example, Ln‐separation
      and recycling or as lanthanide‐binding tags. Optimizing peptides for Ln‐binding can be cumbersome and
      many techniques need high sample volumes. Here short 12‐aminoacid peptides are investigated based on the
      metal‐binding loops of the natural Ln‐binding protein lanmodulin with advanced gas‐phase techniques such
      as ion mobility spectrometry, collision‐induced dissociation, and electrospray ionization to gain
      insight into binding residues and possible differences between sequences. Both the natural sequences as
      well as peptides that are synthesized in “reverse” order are investigated and it is found that the
      trends observed in solution measurements are well reproduced by gas‐phase measurements.

  [22] 10.26434/chemrxiv-2025-q7jl8 | 2025 | chemrxiv | BM25 5.9 | preprint
      Peptide Charge Modulates Ion Binding to EF-Hand Motifs: A Molecular Dynamics Study

      Rare earth elements (REEs), particularly lanthanides (Ln), are of significant interest due to their
      critical roles in modern technology and medicine. However, their extraction, isolation, and purification
      remain challenging. Lanmodulin (LanM), a recently discovered EF-hand protein, exhibits high affinity and
      selectivity for binding Ln3+ ions. This enhanced affinity is partly attributed to the presence of
      additional acidic residues within its EF-hand metal binding loops. Previous studies have demonstrated
      that reducing the number of ligating acidic residues within EF-hand motifs significantly decreases their
      binding affinities for La3+. Yet, the underlying molecular mechanisms remain poorly understood. To
      address this, we performed molecular dynamics (MD) simulations and MMPBSA/MMGBSA analyses on a series of
      EF-hand motifs with varying numbers of ligating acidic residues. Our results reveal that the number of
      acidic ligands strongly influences the structure of the peptide–ion complex. Specifically, a decrease in
      ligating acidic residue leads to increased coordination of water molecules to La3+. We also observed a
      complex interplay among different ligand types, including ligating acidic and neutral residues,
      non-ligating acidic residues, backbone carbonyls, and water molecules. Notably, reducing the number of
      acidic ligands significantly alters the secondary structure of the EF-hand motif, increases its
      flexibility, and reshapes its free energy landscape. This study provides important molecular insights
      into how peptide charge modulates ion binding to EF-hand motifs, offering valuable guidance for the
      rational design of EF-hand proteins with tailored ion-binding properties.

  [23] 10.1101/2023.10.05.559649 | 2023 | crossref | BM25 4.7
      Enhanced Ca 2+ Binding to EF-Hands through Phosphorylation of Conserved Serine Residues Activates MpRBOHB and Chitin-Triggered ROS Production

      Abstract NADPH oxidases/RBOHs catalyze apoplastic ROS production and act as key signaling nodes,
      integrating multiple signal transduction pathways regulating plant development and stress responses.
      Although RBOHs have been suggested to be activated by Ca 2+ binding and phosphorylation by various
      protein kinases, a mechanism linking Ca 2+ binding and phosphorylation in the activity regulation
      remained elusive. Chitin-triggered ROS production required cytosolic Ca 2+ elevation and Ca 2+ binding
      to MpRBOHB in a liverwort Marchantia polymorpha . Heterologous expression analysis of truncated variants
      revealed that a segment of the N-terminal cytosolic region highly conserved among land plant RBOHs
      encompassing the two EF-hand motifs is essential for the activation of MpRBOHB. Within the conserved
      regulatory domain, we have identified two Ser residues whose phosphorylation is critical for the
      activation in planta . Isothermal titration calorimetry analyses revealed that phosphorylation of the
      two Ser residues increased the Ca 2+ binding affinity of MpRBOHB, while Ca 2+ binding is indispensable
      for the activation, even if the two Ser residues are phosphorylated. Our findings shed light on a
      mechanism through which phosphorylation potentiates the Ca 2+ -dependent activation of MpRBOHB,
      emphasizing the pivotal role of Ca 2+ binding in mediating the Ca 2+ and phosphorylation-driven
      activation of MpRBOHB, which is likely to represent a fundamental mechanism conserved among land plant
      RBOHs.

  [24] 10.1096/fasebj.2022.36.s1.r4572 | 2022 | crossref | BM25 3.9
      Investigating Landmodulin's EF Hands in Relation to Lanthanide Recycling Methods

      Rare earth elements (REEs) have distinct and varied electronic properties that have been applied for
      military and civilian use in electronics, such as cell phones and computer chip technologies. The
      recycling methods for REEs are complex and require a multitude of resources that prompt new studies to
      improve REEs separations. Lanmodulin (LanM), a protein that naturally bind to lanthanides, may provide a
      biological route for REE separation. Understanding the structure of LanM’s EF‐hands will explain how the
      lanthanides bond to them and lead to a greater understanding of how LanM can be used to recycle REEs to
      benefit our environment. The Summit Country Day School MSOE Center for BioMolecular Modeling MAPS Team
      used 3D modeling and printing technology to examine structure‐function relationships of EF1‐3 hands on
      lanmodulin. LanM has three tight binding EF‐hands, EF1 (D35‐E46), EF2 (D59‐E70), and EF3 (D84‐ E95),
      which are abundant in carboxylate side chains that bind the lanthanides. Lanthanide binding promotes a
      large conformational shift of the protein from a disorganized state to an organized state. The interior
      of the protein is a condensed helical bundle, and the majority of the exterior is composed of the EF
      hands, making bonding with lanthanides easier due to the EF hands being solely on the exterior. These
      three hands contain a higher number of coordination numbers (8‐9) compared to only 7 in Calmodulin
      (CaM), resulting in more specialized bonding properties. LanM also has a conserved proline between the
      first and second putative metal‐coordinating residues in each of the four EF hands, which is unique to
      this protein and may play a role in reducing affinity for calcium ions. In conclusion, analyzing the
      properties of the binding sites of EF1‐3 in LanM through 3D modeling can reveal insights on utilizing
      proteins as a method to extract and recycle REE in order to be environmentally cognizant.

---

## q1:c7  label:

CLAIM
  Lanthanide-binding proteins of the lanmodulin architecture answer yes to the design rule 'Does it carry at least 4 EF-hand loops?' (measured 4 in A0A4V2JDD3, 4 in C5B164)

EVIDENCE -- 4 passage(s), exactly as the judge sees them
  [25] 10.26434/chemrxiv-2025-q7jl8 | 2025 | chemrxiv | BM25 9.1 | preprint
      Peptide Charge Modulates Ion Binding to EF-Hand Motifs: A Molecular Dynamics Study

      Rare earth elements (REEs), particularly lanthanides (Ln), are of significant interest due to their
      critical roles in modern technology and medicine. However, their extraction, isolation, and purification
      remain challenging. Lanmodulin (LanM), a recently discovered EF-hand protein, exhibits high affinity and
      selectivity for binding Ln3+ ions. This enhanced affinity is partly attributed to the presence of
      additional acidic residues within its EF-hand metal binding loops. Previous studies have demonstrated
      that reducing the number of ligating acidic residues within EF-hand motifs significantly decreases their
      binding affinities for La3+. Yet, the underlying molecular mechanisms remain poorly understood. To
      address this, we performed molecular dynamics (MD) simulations and MMPBSA/MMGBSA analyses on a series of
      EF-hand motifs with varying numbers of ligating acidic residues. Our results reveal that the number of
      acidic ligands strongly influences the structure of the peptide–ion complex. Specifically, a decrease in
      ligating acidic residue leads to increased coordination of water molecules to La3+. We also observed a
      complex interplay among different ligand types, including ligating acidic and neutral residues,
      non-ligating acidic residues, backbone carbonyls, and water molecules. Notably, reducing the number of
      acidic ligands significantly alters the secondary structure of the EF-hand motif, increases its
      flexibility, and reshapes its free energy landscape. This study provides important molecular insights
      into how peptide charge modulates ion binding to EF-hand motifs, offering valuable guidance for the
      rational design of EF-hand proteins with tailored ion-binding properties.

  [26] 10.26434/chemrxiv-2021-36s56 | 2021 | chemrxiv | BM25 8.7 | preprint
      LanM Peptides – Unravelling the Binding Properties of the EF-Hand Loop Sequences Stripped from the Structural Corset

      Since the discovery of the biological relevance of lanthanides (Lns) for methylotrophic bacteria in the
      last decade, the field has seen a steady rise in discoveries of bacteria using Lns. The major role of
      lanthanides here is in the active sites of enzymes: methanol dehydrogenases. Additionally, lanthanide
      binding proteins have also been identified. One such protein is lanmodulin (LanM) and, with a remarkable
      selectivity for Lns over Ca(II) and affinities in the picomolar range, it makes an attractive target to
      address challenges in lanthanide separation. Why LanM has such a high selectivity is currently not
      entirely understood, both the specific amino acid sequences of the EF-hand loops, together with
      cooperativity effects have been suggested. Consequently, we decided to remove the effect of
      cooperativity by focusing on the amino acid level. Thus, we synthesized all four 12-amino acid EF-Hand
      loop peptides of LanM using solid phase peptide synthesis and investigated their affinity for Lns
      (Eu(III), Tb(III)), the actinide Cm(III) and Ca(II). Using isothermal titration calorimetry and time
      resolved laser fluorescence spectroscopy combined with parallel factor analysis, we show that in the
      absence of cooperativity the short EF-Hand loop peptides have all similar affinities for lanthanides and
      that these are all in the micromolar range. Furthermore, calcium was shown not to bind to the peptides
      which was verified with circular dichroism spectroscopy. This technique also revealed that the peptides
      undergo a change to a more ordered state when lanthanides are added. These experimental observations
      were further supported by molecular dynamics simulations. Lastly, we put Eu(III) and Cm(III) in direct
      competition using TRLFS. Remarkably, a slightly higher affinity for the actinide, as was also observed
      for LanM, was found. Our results demonstrate that the picomolar affinities in LanM are largely an effect
      of pre-structuring in the full protein and therefore reduction of flexibility in combination with
      cooperative effects, and that all EF-Hand loops possess similar affinities when detached from the
      protein backbone, albeit still retaining the high selectivity for lanthanides and actinides over
      calcium.

  [27] 10.1002/chem.71438 | 2026 | crossref | BM25 6.6
      Influence of Head‐to‐Tail Cyclization of Lanmodulin‐Inspired Peptides on Lanthanide Affinity and Structure

      ABSTRACT Over the recent years, lanthanide (Ln)‐binding proteins such as lanmodulin, a naturally
      Ln‐binding EF‐hand protein from Methylorubrum extorquens AM1, as well as protein‐inspired short
      Ln‐binding peptides, have become of increasing interest for the development of separation and recycling
      methods for rare earth elements. Here, we comprehensively examined a set of head‐to‐tail cyclized
      lanmodulin‐EF‐hand sequence‐inspired peptides and their complexation behavior toward Lns using
      time‐resolved laser‐induced fluorescence spectroscopy (TRLFS), isothermal titration calorimetry (ITC),
      nuclear magnetic resonance (NMR), and circular dichroism (CD) spectroscopies, complemented by molecular
      dynamic (MD) simulations and advanced mass spectrometry methods. Results obtained from this multi‐method
      approach evidence that the head‐to‐tail cyclization can indeed increase the Ln affinity in some cases
      and positively impact the pre‐organization of the metal‐free peptide while predominantly forming 1:1
      complexes in comparison to linear analogues, which can form both 1:1 and 1:2 species. Furthermore, the
      impact of a sequence alteration by inserting glycine at the head‐to‐tail junction is shown to be useful
      in NMR experiments for probing alterations in the local environment of neighboring amino acids (AA)
      potentially involved in coordination. Lastly, K D values for the peptides with the whole Ln series
      (except Pm) and the actinide curium are presented.

  [28] 10.1021/acs.biochem.6c00566 | 2026 | crossref | BM25 6.1
      EF-Hand Binding Order and Conformational Control of Lanthanide Ion Binding in M. extorquens Lanmodulin

      Abstract Biomolecular chelators have emerged recently as potential alternatives to conventional,
      energy-intensive methods for the challenging separation of rare earth elements (REEs), including the
      lanthanide (LnIII) ions. Lanmodulin (LanM) from Methylobacterium extorquens is the archetype for highly
      selective biological REE chelation and has been applied for recovery and separations of REEs. LanM’s
      high affinity and selectivity are driven by a large disorder-to-order conformational transition in
      response to cooperative binding of LnIII ions to three of its EF-hand motifs, with one site being more
      labile than the other two. Definition of the order of LnIII ion binding and the structural interactions
      contributing to cooperativity has been elusive but is essential for engineering of LanM and other
      REE-binding proteins. Here, we use a combination of mutagenesis and spectroscopic methods (UV
      absorbance, circular dichroism, luminescence, and NMR spectroscopies) to achieve both aims. We identify
      a salt bridge (K93-D56) between LanM’s two primary helices, disruption of which inactivates one of the
      metal-binding sites. Together, our results suggest, contrary to previous hypotheses, that EF1 and EF2
      are the tightest sites, which are sufficient to organize most of the protein’s tertiary structure; EF3
      is the labile, third binding site; and REEs, circumneutral pH, and the salt bridge are all essential for
      LanM’s full conformational change. These results help to define the conformational landscape underlying
      LanM’s selective REE recognition and provide design principles for engineering REE-binding proteins for
      recovery and separation applications.

---

## q1:c8  label:

CLAIM
  Lanthanide-binding proteins of the lanmodulin architecture answer yes to the design rule 'Are two adjacent EF-hands fewer than 14 residues apart?' (measured 12 in A0A4V2JDD3, 12 in C5B164)

EVIDENCE -- 4 passage(s), exactly as the judge sees them
  [29] 10.1096/fasebj.2022.36.s1.r4572 | 2022 | crossref | BM25 11.7
      Investigating Landmodulin's EF Hands in Relation to Lanthanide Recycling Methods

      Rare earth elements (REEs) have distinct and varied electronic properties that have been applied for
      military and civilian use in electronics, such as cell phones and computer chip technologies. The
      recycling methods for REEs are complex and require a multitude of resources that prompt new studies to
      improve REEs separations. Lanmodulin (LanM), a protein that naturally bind to lanthanides, may provide a
      biological route for REE separation. Understanding the structure of LanM’s EF‐hands will explain how the
      lanthanides bond to them and lead to a greater understanding of how LanM can be used to recycle REEs to
      benefit our environment. The Summit Country Day School MSOE Center for BioMolecular Modeling MAPS Team
      used 3D modeling and printing technology to examine structure‐function relationships of EF1‐3 hands on
      lanmodulin. LanM has three tight binding EF‐hands, EF1 (D35‐E46), EF2 (D59‐E70), and EF3 (D84‐ E95),
      which are abundant in carboxylate side chains that bind the lanthanides. Lanthanide binding promotes a
      large conformational shift of the protein from a disorganized state to an organized state. The interior
      of the protein is a condensed helical bundle, and the majority of the exterior is composed of the EF
      hands, making bonding with lanthanides easier due to the EF hands being solely on the exterior. These
      three hands contain a higher number of coordination numbers (8‐9) compared to only 7 in Calmodulin
      (CaM), resulting in more specialized bonding properties. LanM also has a conserved proline between the
      first and second putative metal‐coordinating residues in each of the four EF hands, which is unique to
      this protein and may play a role in reducing affinity for calcium ions. In conclusion, analyzing the
      properties of the binding sites of EF1‐3 in LanM through 3D modeling can reveal insights on utilizing
      proteins as a method to extract and recycle REE in order to be environmentally cognizant.

  [30] 10.26434/chemrxiv-2025-q7jl8 | 2025 | chemrxiv | BM25 9.0 | preprint
      Peptide Charge Modulates Ion Binding to EF-Hand Motifs: A Molecular Dynamics Study

      Rare earth elements (REEs), particularly lanthanides (Ln), are of significant interest due to their
      critical roles in modern technology and medicine. However, their extraction, isolation, and purification
      remain challenging. Lanmodulin (LanM), a recently discovered EF-hand protein, exhibits high affinity and
      selectivity for binding Ln3+ ions. This enhanced affinity is partly attributed to the presence of
      additional acidic residues within its EF-hand metal binding loops. Previous studies have demonstrated
      that reducing the number of ligating acidic residues within EF-hand motifs significantly decreases their
      binding affinities for La3+. Yet, the underlying molecular mechanisms remain poorly understood. To
      address this, we performed molecular dynamics (MD) simulations and MMPBSA/MMGBSA analyses on a series of
      EF-hand motifs with varying numbers of ligating acidic residues. Our results reveal that the number of
      acidic ligands strongly influences the structure of the peptide–ion complex. Specifically, a decrease in
      ligating acidic residue leads to increased coordination of water molecules to La3+. We also observed a
      complex interplay among different ligand types, including ligating acidic and neutral residues,
      non-ligating acidic residues, backbone carbonyls, and water molecules. Notably, reducing the number of
      acidic ligands significantly alters the secondary structure of the EF-hand motif, increases its
      flexibility, and reshapes its free energy landscape. This study provides important molecular insights
      into how peptide charge modulates ion binding to EF-hand motifs, offering valuable guidance for the
      rational design of EF-hand proteins with tailored ion-binding properties.

  [31] 10.1101/2023.10.05.559649 | 2023 | crossref | BM25 8.5
      Enhanced Ca 2+ Binding to EF-Hands through Phosphorylation of Conserved Serine Residues Activates MpRBOHB and Chitin-Triggered ROS Production

      Abstract NADPH oxidases/RBOHs catalyze apoplastic ROS production and act as key signaling nodes,
      integrating multiple signal transduction pathways regulating plant development and stress responses.
      Although RBOHs have been suggested to be activated by Ca 2+ binding and phosphorylation by various
      protein kinases, a mechanism linking Ca 2+ binding and phosphorylation in the activity regulation
      remained elusive. Chitin-triggered ROS production required cytosolic Ca 2+ elevation and Ca 2+ binding
      to MpRBOHB in a liverwort Marchantia polymorpha . Heterologous expression analysis of truncated variants
      revealed that a segment of the N-terminal cytosolic region highly conserved among land plant RBOHs
      encompassing the two EF-hand motifs is essential for the activation of MpRBOHB. Within the conserved
      regulatory domain, we have identified two Ser residues whose phosphorylation is critical for the
      activation in planta . Isothermal titration calorimetry analyses revealed that phosphorylation of the
      two Ser residues increased the Ca 2+ binding affinity of MpRBOHB, while Ca 2+ binding is indispensable
      for the activation, even if the two Ser residues are phosphorylated. Our findings shed light on a
      mechanism through which phosphorylation potentiates the Ca 2+ -dependent activation of MpRBOHB,
      emphasizing the pivotal role of Ca 2+ binding in mediating the Ca 2+ and phosphorylation-driven
      activation of MpRBOHB, which is likely to represent a fundamental mechanism conserved among land plant
      RBOHs.

  [32] 10.1002/ejic.202500258 | 2025 | crossref | BM25 6.0
      Lanthanide‐Binding Lanmodulin‐Based Peptides: Insights from Advanced Mass Spectrometry Techniques

      Selective peptide ligands for lanthanides (Ln) have multiple applications in, for example, Ln‐separation
      and recycling or as lanthanide‐binding tags. Optimizing peptides for Ln‐binding can be cumbersome and
      many techniques need high sample volumes. Here short 12‐aminoacid peptides are investigated based on the
      metal‐binding loops of the natural Ln‐binding protein lanmodulin with advanced gas‐phase techniques such
      as ion mobility spectrometry, collision‐induced dissociation, and electrospray ionization to gain
      insight into binding residues and possible differences between sequences. Both the natural sequences as
      well as peptides that are synthesized in “reverse” order are investigated and it is found that the
      trends observed in solution measurements are well reproduced by gas‐phase measurements.

---

## q1:c9  label:

CLAIM
  Site A201 of 8FNR holds Dy3+ with a mean Dy3+-donor distance of 2.5 A

EVIDENCE -- 4 passage(s), exactly as the judge sees them
  [33] 10.26434/chemrxiv-2025-fkq5s | 2025 | chemrxiv | BM25 8.9 | preprint
      Combining Coordination and Chelation Moieties to Engineer a New Linker for Lanthanide Coordination Chemistry

      Organic linkers play a crucial role in constructing lanthanide (Ln) coordination polymers (CPs),
      influencing structural topologies and physicochemical properties. Herein, we introduce
      6-oxo-1,6-dihydro-2,5-pyridinedicarboxylic acid (2,5-H3PODC) as a new ligand for constructing lanthanide
      coordination polymers that integrates the structural features of terephthalic acid with the chelation
      capabilities of pyridinone-based functional groups. Six lanthanide-based coordination polymers were
      synthesized with 2,5-H3PODC, forming two types of CPs - type 1: [Ln(HPODC)(Ox)0.5(H2O)2] (where (Ox) =
      oxalic acid and Ln = Pr3+ (1), Nd3+ (2)) and type 2: [Ln(H2PODC)(HPODC)(H2O)] (Ln = Eu3+ (3), Gd3+ (4),
      Dy3+ (5), Er3+ (6). All compounds were structurally characterized by single-crystal and powder X-ray
      diffraction, and both compound types are 2D ladder-like networks with cem topologies where the trivalent
      metal centers are bridged via HPODC2- and Ox2- ligands in type 1 structures and H2PODC- and HPODC2-
      linkers in type 2 structures. Thermogravimetric analysis (TGA) demonstrated that compound 2 exhibits
      stability up to 310 °C, while compound 4 exhibits stability up to 325 °C, and the photoluminescent
      properties of 3 were also examined, revealing efficient ligand based sensitization and characteristic
      emission bands for Eu(III).

  [34] 10.26434/chemrxiv.5410921.v1 | 2017 | chemrxiv | BM25 8.7 | preprint
      Bond-length distributions for ions bonded to oxygen: Metalloids and post-transition metals

      Bond-length distributions are examined for thirty-three configurations of the metalloid ions and
      fifty-six configurations of the post-transition-metal ions bonded to oxygen. Lone-pair stereoactivity is
      discussed.

  [35] 10.26434/chemrxiv.5410921.v2 | 2017 | chemrxiv | BM25 8.7 | preprint
      Bond-length distributions for ions bonded to oxygen: Metalloids and post-transition metals

      Bond-length distributions are examined for thirty-three configurations of the metalloid ions and
      fifty-six configurations of the post-transition-metal ions bonded to oxygen. Lone-pair stereoactivity is
      discussed.

  [36] 10.26434/chemrxiv.15001586/v1 | 2026 | chemrxiv | BM25 8.7 | preprint
      Direct evidence of a lanthanide-tellurium bond in [K(18-crown 6)(Cp′′2LnTe3)] with Ln = La, Ce, and Nd

      Using non-classical divalent lanthanide precursors as multi-electron reducing agents, complexes,
      [K(18-crown-6)(Cp” 2 LnTe 3 )], with Ln = La, Ce, and Nd, Cp” =
      1,3-bis-(trimethylsilyl)cyclopentadienyl, were synthesized and investigated to elucidate the mechanism
      of lanthanide-tellurium bonding and the role of 4 f -element electron density in stabilizing small
      chalcogenide chains. Density-Functional Theory (DFT) reveals that the frontier molecular orbitals of
      these complexes are predominantly localized on the [Te 3 ] 2- fragment, while the trivalent lanthanide
      ions stabilize the tellurium chain through weak but measurable metal-ligand interactions. To
      experimentally resolve these interactions, we focus on complementary ligand- and metal-centered X-ray
      spectroscopic approaches. Ln L 3 -edge high-resolution XANES (HR-XANES) and valence-band resonant
      inelastic X-ray scattering (VB-RIXS) demonstrate that the Ln-Te/C interaction has substantial Ln 5 d
      orbitals contribution, particularly for the Ln-Te bond, and remains largely constant across the three
      complexes. DFT-based bond analysis provides a mechanistic interpretation of these trends. The Ln–C
      interaction exhibits increasing electron density at the bond critical point and a higher delocalization
      index (QTAIM analysis) from the lighter to the heavier lanthanides, reflecting enhanced Ln 4 f
      participation within an energy-driven covalency regime. The Ln–Te interaction is predominantly
      electrostatic, with meaningful orbital contributions arising mainly from Ln 5 d participation within an
      orbital-overlap driven covalency regime. These results demonstrate that the Ln-C and Ln-Te bonding in
      the present complexes follow fundamentally distinct covalency mechanisms, which together enable the
      stabilization and isolation of the small [Te 3 ] 2- fragment chain.

---

## q1:c10  label:

CLAIM
  Site A201 of 8FNS holds Nd3+ with a mean Nd3+-donor distance of 2.51 A

EVIDENCE -- 4 passage(s), exactly as the judge sees them
  [37] 10.26434/chemrxiv.6008294.v1 | 2018 | chemrxiv | BM25 8.9 | preprint
      Bright near Infrared Neodymium Emission from Europium Sensitisation in β-Triketonate Coordination Polymers

      Isomorphous β -triketonate-based lanthanoid polymers containing tris(4-methylbenzoyl)methane ( mtbm )
      and RbOH with formula, {[Ln(Rb)( mtbm ) 4 ] 2 } n (Ln = Eu 3+ and Nd 3+ ) have been synthesised and
      structurally characterised. The photophysical properties for the Nd 3+ complex presented long lifetimes
      and relatively high quantum yields in comparison with analogous β -diketonate complexes. Mixed
      lanthanoid complexes were also formed and their luminescence properties studied, with effective
      sensitisation of the 4 F 3/2 of Nd 3+ via the 5 D 0 of Eu 3+ , which is to the best of our knowledge the
      first example of Eu 3+ to Nd 3+ sensitisation in coordination polymers

  [38] 10.26434/chemrxiv.5410921.v1 | 2017 | chemrxiv | BM25 8.7 | preprint
      Bond-length distributions for ions bonded to oxygen: Metalloids and post-transition metals

      Bond-length distributions are examined for thirty-three configurations of the metalloid ions and
      fifty-six configurations of the post-transition-metal ions bonded to oxygen. Lone-pair stereoactivity is
      discussed.

  [39] 10.26434/chemrxiv.5410921.v2 | 2017 | chemrxiv | BM25 8.7 | preprint
      Bond-length distributions for ions bonded to oxygen: Metalloids and post-transition metals

      Bond-length distributions are examined for thirty-three configurations of the metalloid ions and
      fifty-six configurations of the post-transition-metal ions bonded to oxygen. Lone-pair stereoactivity is
      discussed.

  [40] 10.1002/chem.71438 | 2026 | crossref | BM25 8.7
      Influence of Head‐to‐Tail Cyclization of Lanmodulin‐Inspired Peptides on Lanthanide Affinity and Structure

      ABSTRACT Over the recent years, lanthanide (Ln)‐binding proteins such as lanmodulin, a naturally
      Ln‐binding EF‐hand protein from Methylorubrum extorquens AM1, as well as protein‐inspired short
      Ln‐binding peptides, have become of increasing interest for the development of separation and recycling
      methods for rare earth elements. Here, we comprehensively examined a set of head‐to‐tail cyclized
      lanmodulin‐EF‐hand sequence‐inspired peptides and their complexation behavior toward Lns using
      time‐resolved laser‐induced fluorescence spectroscopy (TRLFS), isothermal titration calorimetry (ITC),
      nuclear magnetic resonance (NMR), and circular dichroism (CD) spectroscopies, complemented by molecular
      dynamic (MD) simulations and advanced mass spectrometry methods. Results obtained from this multi‐method
      approach evidence that the head‐to‐tail cyclization can indeed increase the Ln affinity in some cases
      and positively impact the pre‐organization of the metal‐free peptide while predominantly forming 1:1
      complexes in comparison to linear analogues, which can form both 1:1 and 1:2 species. Furthermore, the
      impact of a sequence alteration by inserting glycine at the head‐to‐tail junction is shown to be useful
      in NMR experiments for probing alterations in the local environment of neighboring amino acids (AA)
      potentially involved in coordination. Lastly, K D values for the peptides with the whole Ln series
      (except Pm) and the actinide curium are presented.

---

## q1:c11  label:

CLAIM
  Site A202 of 8FNR holds Dy3+ with a mean Dy3+-donor distance of 2.42 A

EVIDENCE -- 4 passage(s), exactly as the judge sees them
  [41] 10.26434/chemrxiv.5410921.v1 | 2017 | chemrxiv | BM25 8.7 | preprint
      Bond-length distributions for ions bonded to oxygen: Metalloids and post-transition metals

      Bond-length distributions are examined for thirty-three configurations of the metalloid ions and
      fifty-six configurations of the post-transition-metal ions bonded to oxygen. Lone-pair stereoactivity is
      discussed.

  [42] 10.26434/chemrxiv.5410921.v2 | 2017 | chemrxiv | BM25 8.7 | preprint
      Bond-length distributions for ions bonded to oxygen: Metalloids and post-transition metals

      Bond-length distributions are examined for thirty-three configurations of the metalloid ions and
      fifty-six configurations of the post-transition-metal ions bonded to oxygen. Lone-pair stereoactivity is
      discussed.

  [43] 10.1002/chem.71438 | 2026 | crossref | BM25 8.7
      Influence of Head‐to‐Tail Cyclization of Lanmodulin‐Inspired Peptides on Lanthanide Affinity and Structure

      ABSTRACT Over the recent years, lanthanide (Ln)‐binding proteins such as lanmodulin, a naturally
      Ln‐binding EF‐hand protein from Methylorubrum extorquens AM1, as well as protein‐inspired short
      Ln‐binding peptides, have become of increasing interest for the development of separation and recycling
      methods for rare earth elements. Here, we comprehensively examined a set of head‐to‐tail cyclized
      lanmodulin‐EF‐hand sequence‐inspired peptides and their complexation behavior toward Lns using
      time‐resolved laser‐induced fluorescence spectroscopy (TRLFS), isothermal titration calorimetry (ITC),
      nuclear magnetic resonance (NMR), and circular dichroism (CD) spectroscopies, complemented by molecular
      dynamic (MD) simulations and advanced mass spectrometry methods. Results obtained from this multi‐method
      approach evidence that the head‐to‐tail cyclization can indeed increase the Ln affinity in some cases
      and positively impact the pre‐organization of the metal‐free peptide while predominantly forming 1:1
      complexes in comparison to linear analogues, which can form both 1:1 and 1:2 species. Furthermore, the
      impact of a sequence alteration by inserting glycine at the head‐to‐tail junction is shown to be useful
      in NMR experiments for probing alterations in the local environment of neighboring amino acids (AA)
      potentially involved in coordination. Lastly, K D values for the peptides with the whole Ln series
      (except Pm) and the actinide curium are presented.

  [44] 10.26434/chemrxiv-2025-q7jl8 | 2025 | chemrxiv | BM25 8.4 | preprint
      Peptide Charge Modulates Ion Binding to EF-Hand Motifs: A Molecular Dynamics Study

      Rare earth elements (REEs), particularly lanthanides (Ln), are of significant interest due to their
      critical roles in modern technology and medicine. However, their extraction, isolation, and purification
      remain challenging. Lanmodulin (LanM), a recently discovered EF-hand protein, exhibits high affinity and
      selectivity for binding Ln3+ ions. This enhanced affinity is partly attributed to the presence of
      additional acidic residues within its EF-hand metal binding loops. Previous studies have demonstrated
      that reducing the number of ligating acidic residues within EF-hand motifs significantly decreases their
      binding affinities for La3+. Yet, the underlying molecular mechanisms remain poorly understood. To
      address this, we performed molecular dynamics (MD) simulations and MMPBSA/MMGBSA analyses on a series of
      EF-hand motifs with varying numbers of ligating acidic residues. Our results reveal that the number of
      acidic ligands strongly influences the structure of the peptide–ion complex. Specifically, a decrease in
      ligating acidic residue leads to increased coordination of water molecules to La3+. We also observed a
      complex interplay among different ligand types, including ligating acidic and neutral residues,
      non-ligating acidic residues, backbone carbonyls, and water molecules. Notably, reducing the number of
      acidic ligands significantly alters the secondary structure of the EF-hand motif, increases its
      flexibility, and reshapes its free energy landscape. This study provides important molecular insights
      into how peptide charge modulates ion binding to EF-hand motifs, offering valuable guidance for the
      rational design of EF-hand proteins with tailored ion-binding properties.

---

## q1:c12  label:

CLAIM
  Site A202 of 8FNS holds Nd3+ with a mean Nd3+-donor distance of 2.54 A

EVIDENCE -- 4 passage(s), exactly as the judge sees them
  [45] 10.26434/chemrxiv.6008294.v1 | 2018 | chemrxiv | BM25 8.9 | preprint
      Bright near Infrared Neodymium Emission from Europium Sensitisation in β-Triketonate Coordination Polymers

      Isomorphous β -triketonate-based lanthanoid polymers containing tris(4-methylbenzoyl)methane ( mtbm )
      and RbOH with formula, {[Ln(Rb)( mtbm ) 4 ] 2 } n (Ln = Eu 3+ and Nd 3+ ) have been synthesised and
      structurally characterised. The photophysical properties for the Nd 3+ complex presented long lifetimes
      and relatively high quantum yields in comparison with analogous β -diketonate complexes. Mixed
      lanthanoid complexes were also formed and their luminescence properties studied, with effective
      sensitisation of the 4 F 3/2 of Nd 3+ via the 5 D 0 of Eu 3+ , which is to the best of our knowledge the
      first example of Eu 3+ to Nd 3+ sensitisation in coordination polymers

  [46] 10.26434/chemrxiv.5410921.v1 | 2017 | chemrxiv | BM25 8.7 | preprint
      Bond-length distributions for ions bonded to oxygen: Metalloids and post-transition metals

      Bond-length distributions are examined for thirty-three configurations of the metalloid ions and
      fifty-six configurations of the post-transition-metal ions bonded to oxygen. Lone-pair stereoactivity is
      discussed.

  [47] 10.26434/chemrxiv.5410921.v2 | 2017 | chemrxiv | BM25 8.7 | preprint
      Bond-length distributions for ions bonded to oxygen: Metalloids and post-transition metals

      Bond-length distributions are examined for thirty-three configurations of the metalloid ions and
      fifty-six configurations of the post-transition-metal ions bonded to oxygen. Lone-pair stereoactivity is
      discussed.

  [48] 10.1002/chem.71438 | 2026 | crossref | BM25 8.7
      Influence of Head‐to‐Tail Cyclization of Lanmodulin‐Inspired Peptides on Lanthanide Affinity and Structure

      ABSTRACT Over the recent years, lanthanide (Ln)‐binding proteins such as lanmodulin, a naturally
      Ln‐binding EF‐hand protein from Methylorubrum extorquens AM1, as well as protein‐inspired short
      Ln‐binding peptides, have become of increasing interest for the development of separation and recycling
      methods for rare earth elements. Here, we comprehensively examined a set of head‐to‐tail cyclized
      lanmodulin‐EF‐hand sequence‐inspired peptides and their complexation behavior toward Lns using
      time‐resolved laser‐induced fluorescence spectroscopy (TRLFS), isothermal titration calorimetry (ITC),
      nuclear magnetic resonance (NMR), and circular dichroism (CD) spectroscopies, complemented by molecular
      dynamic (MD) simulations and advanced mass spectrometry methods. Results obtained from this multi‐method
      approach evidence that the head‐to‐tail cyclization can indeed increase the Ln affinity in some cases
      and positively impact the pre‐organization of the metal‐free peptide while predominantly forming 1:1
      complexes in comparison to linear analogues, which can form both 1:1 and 1:2 species. Furthermore, the
      impact of a sequence alteration by inserting glycine at the head‐to‐tail junction is shown to be useful
      in NMR experiments for probing alterations in the local environment of neighboring amino acids (AA)
      potentially involved in coordination. Lastly, K D values for the peptides with the whole Ln series
      (except Pm) and the actinide curium are presented.

---
