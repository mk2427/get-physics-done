---
assertion_id: A-002-lin-bfss-virial-eq1
kind: restated-equation
status: Stable
topic: "BFSS matrix model virial theorem — equation 1 (from [H, Tr XP] = 0)"
knowledge_doc_ids:
  - "K-001"
eqn_ref_entries: ["E.1"]
created: 2026-04-27
last_reviewed: 2026-04-27
review_rounds: 3
superseded_by: null

# Differential fields (assertion-specific; see brief 002 §3.4)
# load_bearing: true — this virial equation is a load-bearing constraint in all BFSS bootstrap derivations
load_bearing: true
# derivation_sketch: null on restated-equation; the upstream_ref_hash provides the source pointer
derivation_sketch: null
# upstream_ref_hash: sha256(normalize_eqn_body(r'-2\langle K \rangle + 4\langle V \rangle + \langle F \rangle = 0'))
upstream_ref_hash: "6175215578a76739a1d816cfd07c275a934ae1e1a888fdfe8843deab4e78517b"
# upstream_status_mirror: tracks parent K-doc lifecycle; divergence triggers Under Review
upstream_status_mirror:
  kdoc_id: "K-001"
  kdoc_status_at_stable: "Stable"
  divergence_detected_at: null
---

# Assertion A-002: BFSS Virial Theorem — Equation 1

## Restated Equation

Canonical form (verbatim from K-001 K.5, TeX label `virial_idea`):

$$-2\langle K \rangle + 4\langle V \rangle + \langle F \rangle = 0$$

**Notation key:**

| Symbol | Definition |
|--------|-----------|
| $K$ | Kinetic energy: $K = \frac{g^2}{2}\mathrm{Tr}\,P_I^2$ |
| $V$ | Potential energy: $V = -\frac{1}{4g^2}\mathrm{Tr}\,[X_I,X_J]^2 \ge 0$ |
| $F$ | Fermionic energy: $F = -\frac{1}{2}\mathrm{Tr}\,\psi_\alpha\gamma^I_{\alpha\beta}[X_I,\psi_\beta]$ |
| $\langle \cdot \rangle$ | Expectation value in a quasi-stationary state $\rho$ with $\langle H \rangle = E$ and $[H,\rho] \approx 0$ |
| $\mathrm{Tr}$ | "Big" trace with $\mathrm{Tr}\,\mathbf{1} = N$ (not the normalized little trace $\mathrm{tr} = \mathrm{Tr}/N$) |

The Hamiltonian splits as $H = K + V + F$ per K-001 K.2.

## Regime of Validity

This equation holds under all of the following conditions simultaneously:

1. **BFSS Hamiltonian only.** The equation is derived from $H = K + V + F$ as given in K-001 K.2 (TeX label `ham`). It does NOT hold for the BMN (Berenstein-Maldacena-Nastase) mass-deformed Hamiltonian, which introduces a mass term $\mu^2 \mathrm{Tr}\, X^2 / 2$ that modifies the commutator $[H, \mathrm{Tr}\, XP]$ and changes the virial coefficients.

2. **Quasi-stationary state.** The derivation requires $\langle [H, \mathrm{Tr}\, XP] \rangle = 0$, which holds when $[H, \rho] \approx 0$ (the state is approximately stationary under time evolution). This is NOT the condition for a pure energy eigenstate; it is the condition for a metastable black hole state at large $N$ where commutator expectation values are $1/N$-suppressed. At finite $N$, all excited states are scattering states and $[H,\rho] \approx 0$ is not guaranteed.

3. **SO(9) rotational invariance (for the coefficient interpretation).** The coefficients $-2, 4, 1$ in the equation are directly derived from the degree of $K$ (quadratic in $P$), $V$ (quartic in $X$), and $F$ (bilinear in $\psi$, linear in $X$) under the scaling $X \to t X$, $P \to P/t$. These coefficients do not depend on SO(9) invariance of the state. However, the downstream use of this equation to bound $\langle V \rangle$ via K-001 K.8 DOES require SO(9) invariance.

4. **Any $N$ (no large-$N$ restriction for this equation itself).** The virial relation holds at any $N \ge 2$. Large-$N$ is needed for the quasi-stationarity assumption to be well-controlled (suppressing $[H,\rho]$ by $1/N$) and for the comparison with black hole thermodynamics, but not for the algebraic identity itself.

5. **Traceless Hermitian matrices; $\mathrm{su}(N)$ gauge group.** The matrices $X_I, P_I, \psi_\alpha$ are $N \times N$ Hermitian and traceless, valued in $\mathrm{su}(N)$. Gauge group $\mathrm{U}(N)$ would add a decoupled free center-of-mass sector that does not affect the relative degrees of freedom entering the bootstrap, but the paper works with $\mathrm{SU}(N)$.

6. **Coupling convention.** The Hamiltonian uses the convention where $K = \frac{g^2}{2}\mathrm{Tr}\,P_I^2$ (coupling $g^2$ sits with $K$, not $V$). Changing the coupling-constant convention changes the form of $V$ and $F$ but leaves the virial relation structurally the same (scaling argument is unchanged). See K-001 Conventions for the $g^2$ units ($[g^2] = E^3$).

## Derivation Sketch

This is a `restated-equation` assertion; the full derivation is in K-001 §Derivation Sketches (Sketch 1, Step 2). The mechanism is:

Apply $\langle [H, \mathrm{Tr}\, XP] \rangle = 0$ (quasi-stationarity). Direct computation of the commutator gives:

- $[K, \mathrm{Tr}\, XP] = \frac{g^2}{2}[P^2, XP] \propto -2K$ (two factors of $P$ are affected by the one factor of $X$ in $XP$; each commutation $[P, X] = -i$ contributes a factor of $-i$, so $[P^2, XP] = -2iP^2$; the real coefficient $-2$ in the virial equation emerges after dividing the full commutator relation $\langle [H, \mathrm{Tr}\,XP] \rangle = 0$ through by $i$).
- $[V, \mathrm{Tr}\, XP] \propto +4V$ (the potential $V$ is quartic in $X$; the four factors of $X$ in $V$ each contribute $+1$ from the $X$ in $XP$, giving coefficient $+4$).
- $[F, \mathrm{Tr}\, XP] \propto +F$ (the fermionic term $F$ is linear in $X$ with a single commutator; the one factor of $X$ in $F$ contributes $+1$).

Setting the full commutator expectation to zero yields the asserted equation. The coefficients $-2, 4, 1$ match the Euler scaling weights of $K, V, F$ under $X \to tX, P \to P/t$: kinetic (degree $-2$), potential (degree $+4$), fermionic (degree $+1$). Source paper §2.2, TeX label `virial_idea`, arXiv:2302.04416.

## Sub-Assertions

None.

## Traps and Subtleties

1. **Coefficient signs are easy to mis-copy.** The three coefficients are $-2$, $+4$, $+1$. Common errors:
   - Flipping the sign on the kinetic term (writing $+2\langle K\rangle$ instead of $-2\langle K\rangle$), which would reverse the sense of all downstream inequalities derived from K.5.
   - Writing $+2$ for the fermionic coefficient instead of $+1$, or confusing it with the coefficient in K-001 K.11.
   - Writing the potential coefficient as $+2$ (degree of $V$ in $X$ before commutation) rather than $+4$ (degree of $[X,X]^2$ in $X$). The quartic potential $[X_I,X_J]^2$ has 4 factors of $X$, giving coefficient $+4$, not $+2$.

2. **Quasi-stationarity is required; a pure energy eigenstate is NOT equivalent for the purpose of applying this constraint to Monte Carlo or bootstrap.** The exact statement is $\langle [H, O] \rangle_\rho = 0$ for any operator $O$ when $[H, \rho] = 0$. For a pure energy eigenstate $|\psi\rangle$, this holds exactly. For a quasi-stationary mixed state (the black hole), it holds approximately with corrections suppressed by $1/N$. At finite $N$, all excited states are generically scattering states; $[H,\rho] \approx 0$ must be argued separately. See K-001 §Conventions (State convention) and K-001 §Traps item 2.

3. **This equation alone does not determine $\langle K \rangle$ and $\langle F \rangle$ independently.** K.5 is one equation in three unknowns ($\langle K \rangle, \langle V \rangle, \langle F \rangle$). To resolve $\langle K \rangle$ and $\langle F \rangle$ independently, one must pair K.5 with K-001 K.6 (energy conservation $\langle K \rangle + \langle V \rangle + \langle F \rangle = E$). Together they give:
   $$\langle K \rangle = \tfrac{1}{3}E + \langle V \rangle, \qquad \langle F \rangle = 2\!\left(\tfrac{1}{3}E - \langle V \rangle\right)$$
   (K-001 K.7 and K.11). Using K.5 in isolation to bound $\langle K \rangle$ without invoking K.6 is an error.

4. **The sign of $\langle F \rangle$ is not fixed a priori.** From K-001 K.11, $\langle F \rangle = 2(\frac{1}{3}E - \langle V \rangle)$. If $\langle V \rangle > E/3$ then $\langle F \rangle < 0$, meaning the fermionic contribution acts to lower the energy. This does NOT violate the positivity of $V \ge 0$ (see K-001 §Conventions, Sign of potential $V$). The fermionic term $F$ is bilinear in $\psi$ and has no definite sign. Assuming $\langle F \rangle \ge 0$ without justification is wrong.

5. **Do not confuse $\mathrm{Tr}$ (big trace, $\mathrm{Tr}\,\mathbf{1} = N$) with $\mathrm{tr}$ (little trace, $\mathrm{tr}\,\mathbf{1} = 1$).** The canonical form of K.5 uses $K, V, F$ defined with big-$\mathrm{Tr}$. Virial bounds on dimensionless quantities (e.g., K-001 K.9, K.14) are stated with little-$\mathrm{tr}$ and differ by factors of $N$. Substituting little-trace quantities directly into K.5 without adjusting for the factor of $N$ produces wrong numerical factors.

6. **BMN deformation invalidates this equation.** If the Hamiltonian includes a mass term $H_\mathrm{mass} = \frac{\mu^2}{2}\mathrm{Tr}\,X^2$ (BMN regulator used in Monte Carlo to lift flat directions), the commutator $[H, \mathrm{Tr}\,XP]$ picks up an additional term. By the Euler scaling argument, $H_\mathrm{mass}$ has degree $+2$ under $X\to\lambda X$, $P\to P/\lambda$, so $[H_\mathrm{mass},\mathrm{Tr}\,XP] = i\cdot 2\cdot\tfrac{\mu^2}{2}\mathrm{Tr}\,X^2 = i\mu^2\mathrm{Tr}\,X^2$. Dividing through by $i$ gives an additive correction of $+\mu^2\langle\mathrm{Tr}\,X^2\rangle$. The virial relation for the BMN Hamiltonian is:
$$-2\langle K\rangle + 4\langle V\rangle + \langle F\rangle + \mu^2\langle\mathrm{Tr}\,X^2\rangle = 0$$
Bootstrap bounds from this paper (which assume pure BFSS) will not exactly match Monte Carlo data at finite $\mu$; the discrepancy is an artifact of the BMN regulator, not a violation of the bootstrap.

## Provenance

- **Knowledge docs:** K-001 (`GPD/knowledge/K-001-lin-bfss-bootstrap.md`), equation K.5
- **EQN-REF entries:** E.1 (`GPD/knowledge/013-equation-reference.md`)
- **Source paper:** H. W. Lin, "Bootstrap bounds on D0-brane quantum mechanics," arXiv:2302.04416 [hep-th], §2.2, TeX label `virial_idea`
- **Equation in source:** displayed equation in §2.2 following the sentence "This yields the virial-like relation"; same equation used in Derivation Sketch 1 of K-001 at Step 2
- **upstream_ref_hash:** `6175215578a76739a1d816cfd07c275a934ae1e1a888fdfe8843deab4e78517b` (sha256 of normalized canonical form; pre-computed by orchestrator; do not recompute without re-verifying the canonical_form string verbatim)
