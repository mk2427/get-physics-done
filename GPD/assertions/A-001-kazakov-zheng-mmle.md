---
assertion_id: A-001-kazakov-zheng-mmle
kind: restated-equation
status: Draft
topic: "Makeenko-Migdal loop equations for large-N_c lattice Yang-Mills (Kazakov-Zheng)"
knowledge_doc_ids:
  - "K-003"
eqn_ref_entries: []
created: 2026-04-27
last_reviewed: 2026-04-27
review_rounds: 0
superseded_by: null

# Differential fields (assertion-specific; see brief 002 §3.4)
load_bearing: true
derivation_sketch: null
upstream_ref_hash: "9d246dc8eb8d72ee72e4cc288d49502766c04ec994a18f671bb9b3dd191bbe85"
upstream_status_mirror:
  kdoc_id: "K-003"
  kdoc_status_at_stable: "Stable"
  divergence_detected_at: null
---

# Assertion: Makeenko-Migdal Loop Equations (Kazakov-Zheng)

## Restated Equation

K-label: K-003:(K.3). TeX label in source paper: `MMLE`. Taken verbatim from K-003 §Equations, entry (K.3); no paraphrase.

$$\sum_{\nu \perp \mu} \left( W[C_{l_\mu} \cdot \overrightarrow{\delta C^\nu_{l_\mu}}] - W[C_{l_\mu} \cdot \overleftarrow{\delta C^\nu_{l_\mu}}] \right) = \lambda \sum_{\substack{l' \in C \\ l' \sim l}} \epsilon_{ll'}\, W[C_{ll'}]\, W[C_{l'l}]$$

**Notation.**
- $C$ — an oriented closed lattice loop; $l_\mu \in C$ — a directed link in the $\mu$-direction on $C$.
- $\overrightarrow{\delta C^\nu_{l_\mu}}$ / $\overleftarrow{\delta C^\nu_{l_\mu}}$ — the plaquette in the $\mu\nu$-plane inserted around link $l_\mu$ in the forward / backward transverse direction $\nu$.
- The outer sum on the LHS runs over all $2(D-1)$ transverse directions $\nu \perp \mu$.
- $l' \sim l$ — all occurrences of the same link $l$ in loop $C$ (possibly multiple times if $C$ is self-intersecting); the sum on the RHS runs over all such occurrences.
- $\epsilon_{ll'} = +1$ if $l$ and $l'$ have opposite orientation; $\epsilon_{ll'} = -1$ if they are collinear. (Source: arXiv:2203.11360 §2, p. 2.)
- $C_{ll'}$, $C_{l'l}$ — the two sub-loops formed when $C$ splits at the coincident links $l$ and $l'$.
- $W[C] = \langle (\mathrm{tr}/N_c) \prod_{l \in C} U_l \rangle$ — normalized Wilson loop average (K.2 in K-003).
- $\lambda = g^2 N_c$ — 't Hooft coupling (bare lattice); see Conventions note below.

## Regime of Validity

1. **Gauge group and spacetime**: $SU(N_c)$ lattice Yang-Mills in $D$ dimensions ($D = 2, 3, 4$ studied explicitly in the source paper). Euclidean lattice; all indices spatial. No metric signature issue.

2. **Large-$N_c$ limit**: $N_c \to \infty$ ('t Hooft large-$N$) is essential. The RHS factorizes as $W[C_{ll'}]\,W[C_{l'l}]$ — a product of two Wilson loop averages — only because large-$N_c$ factorization holds: $\langle (\mathrm{tr}/N_c)\,A \cdot (\mathrm{tr}/N_c)\,B \rangle \to W[A]\cdot W[B]$ at $N_c = \infty$. At finite $N_c$, the RHS acquires connected-correlator corrections and the equations no longer close on single-trace WAs.

3. **Coupling regime**: Any value of $\lambda = g^2 N_c$ (weak coupling $\lambda \ll 1$ and strong coupling $\lambda \gg 1$ are both included). The MMLE are exact Schwinger-Dyson equations valid for all $\lambda$.

4. **Action**: Wilson plaquette action $S = -(N_c/\lambda)\sum_P \mathrm{Re}\,\mathrm{tr}\,U_P$ (K.1 in K-003), with the sum running over all plaquettes $P$ in both orientations.

5. **Link variables**: $U_l \in SU(N_c)$; integration over the Haar measure on each link. WAs $W[C]$ are normalized traces at $N_c = \infty$.

## Derivation Sketch

This is a restated-equation assertion; the equation is taken verbatim from K-003 (K.3), which in turn was verified against the TeX source of arXiv:2203.11360 (§2, TeX label `MMLE`). No independent re-derivation is required here; the `upstream_ref_hash` provides the source pointer.

For reference, the derivation recorded in K-003 §Derivation Sketches (Makeenko-Migdal) is as follows. Starting from the partition function $Z = \int \prod_l dU_l\,e^{-S}$ with the Wilson action (K.1), apply the Schwinger-Dyson shift $U_l \to U_l(1 + i\epsilon t^a)$ for each generator $t^a$ of $SU(N_c)$. Haar measure invariance gives $\langle \frac{\delta S}{\delta\epsilon}\,\mathcal{O}\rangle - \langle \frac{\delta \mathcal{O}}{\delta\epsilon}\rangle = 0$ for any operator $\mathcal{O}$. Taking $\mathcal{O}$ to be a Wilson loop containing link $l$ and summing over generators $a$ using the completeness relation $t^a_{ij}t^a_{kl} = \delta_{il}\delta_{jk} - (1/N_c)\delta_{ij}\delta_{kl}$ produces the MMLE. The $1/N_c$ correction drops at $N_c \to \infty$, and the RHS factorizes into the product shown.

## Sub-Assertions

None identified.

## Traps and Subtleties

1. **Sign of $\epsilon_{ll'}$**: The sign convention is $\epsilon_{ll'} = +1$ for opposite orientation, $\epsilon_{ll'} = -1$ for collinear orientation (K-003 §K.3 context, citing arXiv:2203.11360 §2 p. 2). This is easy to flip; always recheck against the source paper before implementing the RHS sum numerically.

2. **Large-$N_c$ factorization is what makes the RHS a product**: At finite $N_c$, the RHS does not simplify to $W[C_{ll'}]\,W[C_{l'l}]$. The product form is purely a consequence of the $N_c \to \infty$ factorization identity. Applying this equation at finite $N_c$ is incorrect.

3. **Back-track loop equations are a separate family**: This assertion covers only the Makeenko-Migdal LEs arising from variation of links in the body of the Wilson loop. Back-track LEs — Schwinger-Dyson equations arising from SD variation of links inserted on back-track paths appended to the loop — are independent and constitute more than 80% of all LEs at practical $L_\mathrm{max}$ values. The MMLE alone do not form a complete constraint set for the bootstrap.

4. **LHS is a sum over $2(D-1)$ transverse directions**: The "loop operator" on the LHS inserts plaquettes in the $\mu\nu$-plane for every direction $\nu \perp \mu$. In $D = 4$, this gives $2 \times 3 = 6$ terms per link per equation (forward and backward for each of the 3 transverse directions). Summing over fewer directions is a common truncation error.

5. **$\lambda = g^2 N_c$ is the bare lattice 't Hooft coupling, not the string tension**: Other papers use $\beta = 2N_c/g^2 = 2N_c^2/\lambda$ (e.g., $\beta_{\rm lat} = 6/g^2 = 6N_c/\lambda$ for $SU(3)$). Kazakov-Zheng do not use $\beta$. When comparing numerical values from other papers, always convert to the same coupling convention. The relation is $\beta = 2N_c^2/\lambda$.

6. **Normalization of trace**: In the WA $W[C] = \langle(\mathrm{tr}/N_c)\prod_{l\in C}U_l\rangle$, the trace is normalized by $1/N_c$. In the Wilson action (K.1), $\mathrm{tr}$ is the unnormalized trace. When substituting $u_P = W[\text{plaquette}]$ back into the action, a factor of $N_c$ must be included: $S = -(N_c^2/\lambda)\sum_P\mathrm{Re}\,u_P$.

7. **Non-physical SDP solutions from convex relaxation**: When these equations are used as constraints in the bootstrap SDP via the convex relaxation (K.5 in K-003), the SDP feasible set is a superset of the true solution set. SDP solutions with $\mathrm{rank}(Q - WW^T) > 0$ satisfy the relaxed MMLE constraints but do not correspond to genuine WA configurations. The bounds are rigorous (they envelope the true solution) but the dual solution cannot be read off as a unique physical WA configuration.

## Provenance

- **Knowledge docs**: K-003 (K-003-kazakov-zheng-lattice-ym-bootstrap.md, status: Stable, review_rounds: 3)
- **EQN-REF entries**: None (no EQN-REF catalog exists; upstream ref tracked via K-label K-003:(K.3) and `upstream_ref_hash`)
- **Source papers**: arXiv:2203.11360 [hep-th], V. Kazakov and Z. Zheng, "Bootstrap for Lattice Yang-Mills theory", §2 (Yang-Mills Loop equations at Large N), TeX equation label `MMLE`. Equation verified against TeX source (not OCR-extracted).
