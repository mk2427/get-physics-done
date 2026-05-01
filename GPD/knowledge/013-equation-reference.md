---
kind: eqn-reference
project: bfss-bootstrap
generated_by: gpd-assertion-digester
meta_audit_report: null
meta_audit_verdict: STUB
eqn_ref_content_hash: null
convention_lock_axes: 0
equation_count: 19
created: 2026-04-27
last_updated: 2026-04-28
---

# EQN-REF Catalog — BFSS Bootstrap (Lin 2023)

**Status: Bootstrap stub.** This catalog was created by the assertion-digester
to enable the divergence gate for A-002. It contains only the equations needed
for existing assertion docs. A full catalog will be produced when the
gpd-eqnref-integrator runs over arXiv:2302.04416.

<!-- §1 Convention Lock: None identified. Full lock to be established by gpd-eqnref-integrator. -->
<!-- §E.0 Translation Formulas: None identified. -->
<!-- §3 Typo Annotations: None identified. -->
<!-- §4 K to E Map: K-001 K.5 maps to E.1; K-001 K.6 maps to E.2; NOTE: both share TeX label virial_idea in source; K-001 K.12 maps to E.9 -->
<!-- §5 Open Questions: None identified. -->
<!-- §6 Traps: None identified. -->

## §2 Equation Catalog

entry_id: E.1
name: BFSS virial theorem — equation 1
source_kdoc: K-001
source_label: virial_idea
source_paper: arXiv:2302.04416
source_section: 2.2
k_label_origin: K-001 K.5
regime: BFSS only; quasi-stationary state; any N>=2
canonical_form: "-2\langle K \rangle + 4\langle V \rangle + \langle F \rangle = 0"

entry_id: E.2
name: BFSS virial theorem — equation 2 (energy conservation)
source_kdoc: K-001
source_label: virial_idea
source_paper: arXiv:2302.04416
source_section: 2.2
k_label_origin: K-001 K.6
regime: any state with <H>=E; any N>=2; BFSS Hamiltonian convention
note: shares TeX label virial_idea with E.1; distinguished by equation content (trivial energy conservation vs non-trivial scaling relation)
canonical_form: "\langle K \rangle + \langle V \rangle + \langle F \rangle = E"

entry_id: E.3
name: BFSS canonical (anti-)commutation relations
source_kdoc: K-001
source_label: canonical
source_paper: arXiv:2302.04416
source_section: 2.1
k_label_origin: K-001 K.1
regime: BFSS Hamiltonian; any N>=2; su(N) gauge group; component fields
note: X_I^A are real non-relativistic bosonic degrees of freedom (component fields, not full matrices); psi_alpha^A are Majorana fermions; A,B run over N^2-1 su(N) generators
canonical_form: "\{ \psi_\alpha^A, \psi_\beta^B \} = \delta^{AB} \delta_{\alpha\beta}, \qquad [X_I^A, P_J^B] = i\, \delta^{AB} \delta_{IJ}"

entry_id: E.4
name: BFSS Hamiltonian
source_kdoc: K-001
source_label: ham
source_paper: arXiv:2302.04416
source_section: 2.1
k_label_origin: K-001 K.2
regime: BFSS only; any N>=2; su(N) gauge group; implicit sum I,J=1..9 and alpha,beta=1..16; units X~E, g^2~E^3
note: Splits as H=K+V+F where K=g^2/2 Tr P_I^2, V=-1/(4g^2) Tr[X_I,X_J]^2, F=-1/2 Tr psi_alpha gamma^I_{alphabeta}[X_I,psi_beta]. All matrices NxN Hermitian traceless.
canonical_form: "H = \frac{1}{2} \operatorname{Tr}\!\left( g^2 P_I^2 - \frac{1}{2g^2} [X_I, X_J]^2 - \psi_\alpha \gamma^I_{\alpha\beta} [X_I, \psi_\beta] \right)"

entry_id: E.5
name: BFSS black hole thermodynamics (gravity dual, 't Hooft limit)
source_kdoc: K-001
source_label: thermo
source_paper: arXiv:2302.04416
source_section: 2.1
k_label_origin: K-001 K.3
regime: gravity regime T^3 << lambda; 't Hooft limit N->infinity lambda fixed; Einstein frame 16*pi*G_N=(2*pi)^7*(alpha')^4
note: Derived from Bekenstein-Hawking entropy in the Einstein frame. Sets the energy scale E/N^2 ~ lambda^{1/3} for the gravity-to-string transition. Above T ~ lambda^{1/3} the supergravity approximation breaks down. Source: Itzhaki-Maldacena-Sonnenschein-Yankielowicz 1998 (arXiv:hep-th/9802042).
canonical_form: "\frac{E}{N^2} = \lambda^{1/3} \frac{9}{14} 4^{13/5} 15^{2/5} \!\left(\frac{\pi}{7}\right)^{14/5}\!\! \left(\frac{T}{\lambda^{1/3}}\right)^{14/5}"

entry_id: E.6
name: BFSS Polchinski bosonic lower bound on ⟨tr X̃⁴⟩
source_kdoc: K-001
source_label: Polchinski
source_paper: arXiv:2302.04416
source_section: 2.2
k_label_origin: K-001 K.9
regime: SO(9)-invariant BFSS states; any E≥0; dimensionless units X̃=λ^{-1/3}X, ε=λ^{-1/3}E/N², tr 1=1
note: Derived by combining: positivity matrix M_1⪰0 (K.4), kinetic energy relation (K.7), and commutator bound V≤72/g² ⟨Tr X⁴⟩ from (K.8); the coefficient 144 enters K.9 via the 2V term in K.7 (2⟨V⟩≤144/g² ⟨Tr X⁴⟩). At ε=0 gives ⟨tr X̃⁴⟩≥1/16 (Polchinski 1999). Improved by (K.17) using fermionic constraints.
canonical_form: "\langle \mathrm{tr}\, \tilde{X}^4 \rangle^{1/2} \left( 144\, \langle \mathrm{tr}\, \tilde{X}^4 \rangle + \frac{2}{3} \mathcal{E} \right) \ge \frac{9}{4}"

entry_id: E.7
name: BFSS fermionic operator rewrite (O_I definition)
source_kdoc: K-001
source_label: (no TeX label; inline equation in §2.3 running text)
source_paper: arXiv:2302.04416
source_section: 2.3
k_label_origin: K-001 K.10
regime: BFSS Hamiltonian; any N≥2; su(N) gauge group; 16 Majorana spinors; SO(9) gamma matrices real symmetric
note: Defines the auxiliary bilinear fermionic operator O_I = (1/2) gamma^I_{alpha beta} {psi^alpha, psi^beta}, so that the fermionic Hamiltonian piece F = Tr O_I X^I. Key consequence: ⟨Tr O^I P_I⟩ = 0 from ⟨[H,F]⟩=0, zeroing the (1,3) entry of M_2 (K.12). No TeX label in source; definition is eq. (16) in arXiv:2302.04416 (flat sequential numbering), appearing in running text of §2.3 between eq. (15) [⟨F⟩ = 2(E/3 - ⟨V⟩)] and eq. (17) [M_2 ⪰ 0].
canonical_form: "F = \frac{1}{2} \gamma^I_{\alpha\beta} \, \mathrm{Tr}\left( \{\psi^\alpha, \psi^\beta\} X^I \right) \equiv \mathrm{Tr}\, O_I X^I"

entry_id: E.8
name: BFSS uncertainty-principle positivity matrix (Round 1)
source_kdoc: K-001
source_label: uncertain
source_paper: arXiv:2302.04416
source_section: 2.2
k_label_origin: K-001 K.4
regime: BFSS; SO(9)-invariant state; any N>=2; quasi-stationary state (⟨[H, Tr X²]⟩=0)
note: Off-diagonal entries ⟨Tr XP⟩ = iN²/2 and ⟨Tr PX⟩ = -iN²/2 follow from ⟨[H, Tr X²]⟩=0 and canonical commutation relations E.3. Factor 9 from summing over all 9 SO(9) bosonic matrices. The matrix M_1 ⪰ 0 is an intermediate step; the final inequality is the load-bearing claim. The M_1 label used in downstream assertions (e.g., A-008) distinguishes this matrix from M_2 (K.12/E.9). Polchinski (1999) had a factor-of-4 error (9/16 instead of 9/4) in the analogous bound; the coefficient 9/4 here is correct (Lin 2023, footnote 4).
canonical_form: "\mathcal{M}_1 = \begin{pmatrix} \langle \mathrm{Tr}\, X^2 \rangle & \langle \mathrm{Tr}\, XP \rangle \\ \langle \mathrm{Tr}\, PX \rangle & \langle \mathrm{Tr}\, P^2 \rangle \end{pmatrix} \succeq 0 \quad \Longrightarrow \quad \sum_{I=1}^{9} \langle \mathrm{Tr}\, X_I^2 \rangle\, \langle \mathrm{Tr}\, P_I^2 \rangle \ge \frac{9}{4} N^4"

entry_id: E.9
name: BFSS central positivity matrix M_2 (bootstrap SDP core)
source_kdoc: K-001
source_label: Cm2
source_paper: arXiv:2302.04416
source_section: 2.3
k_label_origin: K-001 K.12
regime: BFSS; quasi-stationary state ⟨[H,ρ]⟩≈0; any N≥2; SO(9)-invariant state; H=K+V+F decomposition used; virial identities E.1+E.2 used to populate (1,2) and (3,3) entries; fermionic operator E.7 used to zero (1,3) entry
note: Rows/columns correspond (schematically) to operators O_I (fermionic bilinear), X_I (bosonic), P_I (bosonic momentum). The (2,3) entry iN²/2 comes from ⟨Tr XP⟩=iN²/2 derived from CCR E.3 via ⟨[H, Tr X²]⟩=0. The (1,3) zero comes from ⟨Tr O^I P_I⟩=0 from ⟨[H,F]⟩=0 (E.7). The (1,2) entry (2/9)(E/3-⟨V⟩) = (2/9)⟨F⟩/2 uses K.11 (fev identity). The (3,3) entry (2/9)(E/3+⟨V⟩) = (2/9)⟨K⟩ uses K.7 (kinetic_pot). The (1,1) entry ⟨Tr O_I O_I⟩/9 is bounded above by the fermionic SDP (K.13: ≤64N³). Setting det(M_2)=0 at the optimization boundary, combined with K.13 saturated, yields the lower bound on ⟨tr X̃²⟩ (K.14–K.15). The SO(9) factor 1/9 in the (1,1) entry arises from averaging over the 9 spatial directions. Downstream assertion: A-012 (Draft).
canonical_form: "\mathcal{M}_2 = \begin{pmatrix} \tfrac{1}{9}\langle \mathrm{Tr}\, O_I O_I \rangle & \tfrac{2}{9}\!\left(\tfrac{1}{3}E - \langle V \rangle\right) & 0 \\ \tfrac{2}{9}\!\left(\tfrac{1}{3}E - \langle V \rangle\right) & \langle \mathrm{Tr}\, X^2 \rangle & \tfrac{i}{2} N^2 \\ 0 & -\tfrac{i}{2} N^2 & \tfrac{2}{9}\!\left(\tfrac{1}{3}E + \langle V \rangle\right) \end{pmatrix} \succeq 0"

entry_id: E.10
name: BFSS fermionic operator bound (Majorana SDP)
source_kdoc: K-001
source_label: fermionBd
source_paper: arXiv:2302.04416
source_section: 2.3
k_label_origin: K-001 K.13
regime: BFSS; SU(N) gauge group; 16 Majorana spinors with Tr(T^A T^B)=delta^{AB} normalization; any N≥2; large-N limit used for the bound (exact result is ≤64(1-ε')N³ with ε'→0 as N→∞; Lin 2023 drops ε' for the large-N analysis); SO(9) invariance of the state required for the first equality (γ² diagonal with ±1 eigenvalues)
note: The first equality uses the diagonal structure of γ²: s_α=+1 for α=1..8, s_α=-1 for α=9..16, so (1/9)⟨Tr O_I O_I⟩ = ⟨Tr O_2 O_2⟩ = Σ_{α,β} s_α s_β ⟨Tr ψ_α² ψ_β²⟩. The bound ≤64N³ is derived by maximizing Σ s_α s_β M_{αβ} subject to the (1+16)×(1+16) positivity matrix 𝒩⪰0 (K.22), with diagonal entries from K.19-K.20 and off-diagonal entries bounded by K.21 (all in K-001). The bound is tighter than naive O(N⁴) because Majorana anticommutator identities kill many terms. Source TeX label result4 (Appendix C). This entry bounds the (1,1) entry of M_2 (E.9); it is the key constraint that closes the SDP for ⟨tr X̃²⟩. Downstream assertion: A-013 (Draft).
canonical_form: "\frac{1}{9}\langle \mathrm{Tr}\, O_I O_I \rangle = \langle \mathrm{Tr}\, O_2 O_2 \rangle = \sum_{\alpha,\beta} s_\alpha s_\beta \langle \mathrm{Tr}\, \psi_\alpha^2 \psi_\beta^2 \rangle \le 64 N^3"

entry_id: E.11
name: BFSS lower bound on ⟨tr X̃²⟩ — first-line parametric inequality (K.14)
source_kdoc: K-001
source_label: firstLine
source_paper: arXiv:2302.04416
source_section: 2.3
k_label_origin: K-001 K.14
regime: BFSS; SO(9)-invariant state; any N≥2; quasi-stationary state ⟨[H,ρ]⟩≈0; dimensionless units X̃=λ^{-1/3}X, 𝒜=λ^{-1/3}E/N², tr 1=1; v=λ^{-1/3}⟨V⟩/N² (dimensionless potential energy, free parameter); requires 𝒜+3v>0 for denominator regularity
note: K.14 is the "first line" of a two-equation pair (K.14–K.15). The RHS is derived from det(M_2)=0 at the SDP boundary with the fermionic bound E.10 saturated (K.13). The paired constraint K.15 (E.12) fixes the optimal v that minimizes the RHS; at 𝒜=0 and optimal v, the bound gives ⟨tr X̃²⟩≥3/16≈0.1875. The variable v is NOT stated explicitly in the source as v=λ^{-1/3}⟨V⟩/N²; this is inferred from dimensional analysis and the relation v=72⟨tr X̃⁴⟩ (source line 374; K-001 K.14 context). The bound is load-bearing for the main BFSS bootstrap result. Upstream inputs: E.9 (M_2 positivity), E.10 (fermionic operator bound), E.1–E.2 (virial identities), E.6 (commutator/Polchinski bound). Downstream assertion: A-014 (Draft).
canonical_form: "\langle \mathrm{tr}\, \tilde{X}^2 \rangle \ge \frac{(\mathcal{E} - 3v)^2}{9^3 \times 16} + \frac{27}{8(\mathcal{E} + 3v)}"

entry_id: E.12
name: BFSS lower bound on ⟨tr X̃²⟩ — constraint on optimal v (K.15)
source_kdoc: K-001
source_label: secondLine
source_paper: arXiv:2302.04416
source_section: 2.3
k_label_origin: K-001 K.15
regime: BFSS; SO(9)-invariant state; any N≥2; quasi-stationary state ⟨[H,ρ]⟩≈0; dimensionless units 𝒜=λ^{-1/3}E/N², v=λ^{-1/3}⟨V⟩/N²; requires 𝒜+3v>0; v≥0 (since ⟨V⟩≥0)
note: K.15 is the "second line" of the K.14–K.15 pair (TeX label secondLine, §2.3). It is the constraint that fixes the optimal v* minimizing the RHS of K.14 (E.11), arising from ∂/∂v(RHS of K.14)=0 at the det(M_2)=0 boundary. At 𝒜=0, the system K.14+K.15 gives ⟨tr X̃²⟩≥3/16≈0.1875 (the main BFSS bootstrap result). Without K.15, K.14 alone provides only a parametric family indexed by v; the actual lower bound on ⟨tr X̃²⟩ requires solving both equations simultaneously. Paired with E.11 (K.14); downstream assertion: A-015.
canonical_form: "\mathcal{E}^2 + \frac{3^9}{\mathcal{E} + 3v} = 9v^2"

entry_id: E.13
name: BFSS two-sided bound on γ (commutator non-commutativity ratio)
source_kdoc: K-001
source_label: gammaBd
source_paper: arXiv:2302.04416
source_section: 2.3
k_label_origin: K-001 K.16
regime: BFSS; SO(9)-invariant state; any N≥2; quasi-stationary state ⟨[H,ρ]⟩≈0; dimensionless units X̃=λ^{-1/3}X, 𝒜=λ^{-1/3}E/N², tr 1=1; v_γ>0 and 𝒜+3v_γ>0 required for denominator regularity
note: γ measures the non-commutativity of X and Y relative to their individual magnitudes. Lower bound γ≥0 is trivial: -⟨tr[X,Y]²⟩ = ⟨tr(-[X,Y]²)⟩ ≥ 0 because -[X,Y]² = M² ≥ 0 (with M Hermitian: [X,Y]=iM). Upper bound derived by reusing the det(M₂)=0 boundary of K.14/E.11: at the boundary, γ is maximized over v at v=v_γ satisfying the side condition (𝒜-3v_γ)(𝒜+3v_γ)²=2×3⁹. This is the only quantity in Lin 2023 for which a two-sided bootstrap bound is achieved. For SO(9)-invariant states, ⟨tr X²⟩=⟨tr Y²⟩ so the denominator equals ⟨tr X²⟩². Upstream: E.9 (M₂ positivity), E.10 (fermionic operator bound), E.11 (K.14 first line), E.12 (K.15 optimal v); also K-001 K.8 (commutator bound v=72⟨tr X̃⁴⟩).
canonical_form: "\gamma = \frac{-\langle \mathrm{tr}\, [X, Y]^2 \rangle}{\langle \mathrm{tr}\, X^2 \rangle \langle \mathrm{tr}\, Y^2 \rangle}, \qquad 0 \le \gamma \le \frac{v_\gamma}{18} \left[ \frac{4(\mathcal{E} - 3v_\gamma)^2}{9^3 \times 16} + \frac{27}{8(\mathcal{E} + 3v_\gamma)} \right]^{-2}"

entry_id: E.14
name: BFSS improved lower bound on ⟨tr X̃⁴⟩ using fermionic constraints (bigEconstr)
source_kdoc: K-001
source_label: bigEconstr
source_paper: arXiv:2302.04416
source_section: 2.3
k_label_origin: K-001 K.17
regime: BFSS; SO(9)-invariant state; any N≥2; quasi-stationary state ⟨[H,ρ]⟩≈0; dimensionless units X̃=λ^{-1/3}X, 𝒜=λ^{-1/3}E/N², tr 1=1; v=72(t₂)²≥0; 𝒜+3v>0 and 12√(2v)>(𝒜/9-v/3)² required for the constraint bracket to be positive
note: Improves the Polchinski bound E.6 by incorporating fermionic constraints via det(M₂)=0 (E.9) with v=72(t₂)² from K.8 saturated. The optimization parameter t₂ satisfies (t₂)²=⟨tr X̃⁴⟩ at the boundary. At 𝒜=0 this gives ⟨tr X̃⁴⟩≥((7-4√3)/256)^{1/3}≈0.06546, improving the Polchinski value 1/16=0.0625. Upstream: E.6 (Polchinski bosonic bound K.9), E.9 (M₂ positivity K.12), E.10 (fermionic bound K.13); K-001 K.8 (commutator bound providing v=72⟨tr X̃⁴⟩ at saturation). Source TeX label `bigEconstr`, §2.3. The two-equation system (bound plus constraint) together define the improved bound implicitly; neither equation alone constitutes the result. Downstream assertion: A-017.
canonical_form: "\langle \mathrm{tr}\, \tilde{X}^4 \rangle \ge (t_2)^2, \qquad v = 72(t_2)^2, \qquad \left(\frac{\mathcal{E}}{9} + \frac{v}{3}\right) \left(12\sqrt{2v} - \left(\frac{\mathcal{E}}{9} - \frac{v}{3}\right)^2\right) = 54"

entry_id: E.15
name: BFSS SU(N) generator normalization and Casimir identities (Appendix C)
source_kdoc: K-001
source_label: ttCas
source_paper: arXiv:2302.04416
source_section: Appendix C
k_label_origin: K-001 K.18
regime: SU(N) gauge group; any N≥2; generator normalization Tr(T^A T^B)=δ^{AB} (non-standard; differs from the physics convention 1/2*δ^{AB}); BFSS Majorana fermionic content
note: Three identities: (i) normalization Tr(T^A T^B)=δ^{AB} (TeX label `majorana`; a convention choice throughout the paper, not a derivable fact); (ii) quadratic Casimir T^A T^A=(N^2-1)/N (first identity in `ttCas`; follows from completeness of su(N) generators with normalization (i)); (iii) quartic generator identity Tr(T^A T^B T^A T^C)=-(1/N)δ^{BC} (second identity in `ttCas`; non-trivial computation from su(N) Lie algebra, used to derive Tr Ψ^4 in K.20 and off-diagonal fermionic bounds in K.21). All three are required for the Appendix C chain K.18→K.19→K.20→K.21→K.22→result4 that proves the fermionic SDP bound (E.10). Load-bearing upstream dependency of A-013. Changing the normalization convention (i) changes the Casimir values and the final coefficient 64 in E.10/K.13.
canonical_form: "\mathrm{Tr}(T^A T^B) = \delta^{AB}, \qquad T^A T^A = \frac{N^2-1}{N}, \qquad \mathrm{Tr}\, T^A T^B T^A T^C = -\frac{1}{N}\delta^{BC}"
entry_id: E.16
name: BFSS quartic fermionic matrix trace identity Tr Ψ⁴ (K.20, psi4)
source_kdoc: K-001
source_label: psi4
source_paper: arXiv:2302.04416
source_section: Appendix C
k_label_origin: K-001 K.20
regime: SU(N) gauge group; any N≥1; Majorana fermions with {ψ_α^A, ψ_α^B}=δ^{AB} (K.1); generator normalization Tr(T^A T^B)=δ^{AB} (K.18); Ψ=ψ_α for a single fixed spinor index α, no sum over α; no dynamical or state assumptions; purely algebraic
note: Derived by expanding Tr Ψ⁴ = Ψ^A Ψ^B Ψ^C Ψ^D Tr(T^A T^B T^C T^D) and reducing via the Majorana anticommutator (ψ^A)²=1/2 and both Casimir identities from K.18 (E.15): the normalization Tr(T^A T^B)=δ^{AB} and the quartic identity Tr(T^A T^B T^A T^C)=-(1/N)δ^{BC}. The negative sign in the quartic identity produces the -3N²/2 correction and ensures the strict inequality <N³/2 for all N≥1 (gap = (3N²-1)/(4N) > 0). This identity fixes the diagonal entries M_{αα} = N^{-3} Tr ψ_α⁴ of the lower-right 16×16 block of the positivity matrix 𝒩 (K.22), used in the fermionic SDP that proves the operator bound K.13 (E.10). Source: arXiv:2302.04416, Appendix C, TeX label psi4. Downstream assertion: A-020.
canonical_form: "\mathrm{Tr}\,\Psi^4 = \frac{1}{2N}\!\left(N^4 - \frac{3N^2}{2} + \frac{1}{2}\right) < \frac{1}{2}N^3"

entry_id: E.17
name: BFSS off-diagonal fermionic correlator bound (K.21, posAB)
source_kdoc: K-001
source_label: posAB
source_paper: arXiv:2302.04416
source_section: Appendix C
k_label_origin: K-001 K.21
regime: SU(N) gauge group; any N≥2; Majorana fermions with {ψ_α^A, ψ_β^B}=δ^{AB}δ_{αβ} (K.1); generator normalization Tr(T^A T^B)=δ^{AB} (K.18); Ψ=ψ_α, Φ=ψ_β with α≠β (two DISTINCT spinor indices); no dynamical or state assumptions; purely algebraic
note: Derived by (i) using the Majorana anticommutator to anti-symmetrize the four-fermion product Ψ^A Ψ^B Φ^C Φ^D, and (ii) applying the quartic generator identity Tr(T^A T^B T^A T^C)=-(1/N)δ^{BC} (K.18/E.15). The equality Tr(Ψ²Φ²) = -Tr(ΨΦ)(ΨΦ)† + (N²-1)²/(2N²) is an algebraic identity (correctly transcribed from source TeX line 711-713). The `< 1/2` in the canonical form is NOT a bound on Tr(Ψ²Φ²) directly (that expression equals up to (N²-1)²/(2N²) ≈ N²/2 at large N); it is a bound on the SDP matrix entry M_{αβ} = N^{-3}⟨Tr(Ψ²Φ²)⟩ after the N^{-3} normalization from K.22. Correct chain: M_{αβ} ≤ N^{-3}·(N²-1)²/(2N²) = (N²-1)²/(2N⁵) < 1/2, where the last step follows from (N²-1)² < N⁵ for all N≥2 (verified: N=2: 9<32; N=3: 64<243; large N: N⁴<N⁵). Source arXiv:2302.04416 line 726 confirms: posAB bounds M_{αβ}<1/2 for α≠β. This constrains the off-diagonal entries of the 16×16 block of 𝒩 (K.22). Together with K.19 (first row/column) and K.20 (diagonal), fully constrains 𝒩 for the fermionic SDP underlying K.13 (E.10). Source: arXiv:2302.04416, Appendix C, TeX label posAB. Downstream assertion: A-021.
canonical_form: "\Psi^A \Psi^B \Phi^C \Phi^D \, \mathrm{Tr}\, T^A T^B T^C T^D = -\mathrm{Tr}(\Psi\Phi)(\Psi\Phi)^\dagger + \frac{(N^2-1)^2}{2N^2} < \frac{1}{2}"

entry_id: E.18
name: BFSS fermionic positivity matrix 𝒩 (SDP constraint, K.22 / MAB)
source_kdoc: K-001
source_label: MAB
source_paper: arXiv:2302.04416
source_section: Appendix C
k_label_origin: K-001 K.22
regime: BFSS; SU(N) gauge group; 16 Majorana spinors (α,β=1..16); generator normalization Tr(T^A T^B)=δ^{AB} (K.18); any N≥2; quasi-stationary state ⟨[H,ρ]⟩≈0; big-Trace Tr with Tr 1=N; no large-N assumption (entries exact for all N≥2)
note: The (1+16)×(1+16) positivity matrix 𝒩 assembles the fermionic bootstrap SDP. First row/column fixed by K.19 (E.?): N^{-2}Tr(ψ_α)² = (N²-1)/(2N²) ≈ 1/2 at large N. Diagonal 16×16 block M_{αα} fixed by K.20 (E.16): M_{αα} = N^{-3}Tr ψ_α⁴ < 1/2 (A-020). Off-diagonal entries M_{αβ} (α≠β) bounded by K.21 (E.17): M_{αβ} = N^{-3}⟨Tr ψ_α² ψ_β²⟩ < 1/2 (A-021). Positivity 𝒩⪰0 is the bootstrap constraint. The SDP over 𝒩 maximizes Σ_{α,β} s_α s_β M_{αβ} subject to all constraints (K.19–K.21), giving the fermionic operator bound K.13 ≤64N³ (E.10). TeX label MAB, Appendix C. Upstream assertions: A-018 (K.18), A-019 (K.19), A-020 (K.20), A-021 (K.21). Downstream assertion: A-022 (this entry).
canonical_form: "\mathcal{N} = \begin{pmatrix} 1 & N^{-2}\,\mathrm{Tr}(\psi_\alpha)^2 \\ N^{-2}\,\mathrm{Tr}(\psi_\alpha)^2 & \mathcal{M}_{\alpha\beta} \end{pmatrix} \succeq 0, \qquad \mathcal{M}_{\alpha\beta} = \frac{1}{N^3}\langle \mathrm{Tr}\,\psi_\alpha^2 \psi_\beta^2 \rangle"

entry_id: E.19
name: BFSS stronger SO(9) lower bound on ⟨tr X⁴⟩ from positivity matrix M₄ (K.23, strongerSO9)
source_kdoc: K-001
source_label: strongerSO9
source_paper: arXiv:2302.04416
source_section: Appendix D
k_label_origin: K-001 K.23
regime: BFSS; SO(9)-invariant state; any N≥2; quasi-stationary state ⟨[H,ρ]⟩≈0; dimensionful X (not X̃); little-trace tr=Tr/N, tr 1=1; equation homogeneous of degree 4 in X so also valid for X̃ if all terms rescaled simultaneously; D=9 bosonic matrices; does NOT depend on energy 𝒜 or fermionic content
note: Derived in Appendix D of arXiv:2302.04416 by constructing the full positivity matrix M₄ over operators {1, X^I, X^I X^J} and imposing SO(9) rotational invariance. The SO(9) singlet structure reduces all quartic correlators to two parameters A_4, B_4 via ⟨Tr(X^I X^J X^K X^L)⟩ = A_4(δ^{IJ}δ^{KL}+δ^{JK}δ^{IL}) + B_4δ^{IK}δ^{JL}, with Tr X^4=2A_4+B_4 and Tr[X,Y]²=2(B_4-A_4). The max of two bounds corresponds to two different inequalities from the positivity matrix. Constant 27/11 is D=9-specific. The weaker corollary ⟨tr X⁴⟩≥⟨tr X²⟩² follows immediately by dropping the commutator term. The paper notes this bound does NOT improve Figure 1 (the main bootstrap bounds) but is a rigorous derivation. Upstream: K-001 K.8 (commutator bound); K-001 K.12 / E.9 (M₂ positivity) for context; M₄ is a new object not appearing elsewhere in the catalog. Downstream assertion: A-023.
canonical_form: "\langle\mathrm{tr}\,X^4\rangle \ge \max\!\left\{-\tfrac{1}{4}\langle\mathrm{tr}\,[X,Y]^2\rangle,\;\; \tfrac{4}{11}\langle\mathrm{tr}\,[X,Y]^2\rangle + \tfrac{27}{11}\langle\mathrm{tr}\,X^2\rangle^2 \right\}"
