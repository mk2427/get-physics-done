---
kdoc_id: K-002-adams-thermal-conic-bootstrap
status: Stable
topic: "Thermal bootstrap of large-N matrix quantum mechanics via conic optimization (Adams 2025)"
cluster: "bfss-bootstrap"
sources:
  - "arXiv:2511.01209 [hep-th] — S. M. Adams, 'Thermal Bootstrap of Large-N Matrix Models via Conic Optimization'"
created: 2026-04-27
last_reviewed: 2026-04-28
review_rounds: 4
superseded_by: null
eqn_ref_schema_version: 1
assertion_schema_version: 1
layout: single
---

# Knowledge: Thermal Bootstrap of Large-N Matrix Models via Conic Optimization (Adams 2025)

## Overview

This document covers Adams (arXiv:2511.01209), which advances thermal bootstrapping of large-$N$ matrix quantum mechanics (MQM) by replacing the linear SDP approach (with logarithmic relaxation of the KMS condition) with a nonlinear conic solver, QICS, that handles the operator relative entropy cone exactly. The paper targets the one-matrix and two-matrix quartic anharmonic oscillators in the large-$N$ 't Hooft limit, obtaining tighter energy bounds than previously achieved and reaching system sizes where conventional linear SDP solvers become numerically unstable.

The key physical advance is that the thermal KMS condition is an operator relative entropy cone constraint, which previous work (Cho et al., [arXiv ID TBD; bib key: cho2025thermalbootstrapmatrixquantum]) handled by a global logarithmic relaxation $\log x \approx r_{m,k}(x)$. QICS (He et al., arXiv:2407.xxxxx [he2024qicsquantuminformationconic in the source .bib]) implements an interior-point algorithm (Skajaa–Ye + Hypatia stepping) that directly enforces the nonlinear cone without global approximation. This avoids the numerical instability introduced by the linearization at large truncation levels $L$.

For the one-matrix model at coupling $g=2$ and system size $L=12$ (operator products up to length 6), QICS produces energy bounds tight enough to extract three low-temperature long-string parameters via fitting: the ground-state energy $e_0$, the first excited energy gap $\Delta_1$, and the first coupling coefficient $h_{1111}$. The extracted values agree with independent analytic/numerical results (Marchesini & Onofri 1978) to high precision. The two-matrix bootstrap remains numerically challenging at $L=6$, but imposing $U(1)$ symmetry via complex operators substantially reduces the variable count and enables progress.

For this project (BFSS bootstrap), this paper is a direct methodological predecessor and provides: (i) the conic formulation of the KMS constraint to compare against, (ii) benchmarks on the one-matrix and two-matrix anharmonic oscillators that can serve as validation targets, and (iii) the long-string effective theory framework for extracting physical parameters from bootstrap bounds.

## Physical Picture

**Motivation.** Matrix quantum mechanics bootstrapping aims to extract physical observables (energy spectrum, thermal free energy) from consistency conditions alone — symmetries, canonical commutation relations, and the KMS condition — without Monte Carlo or perturbative approximations. At finite temperature the thermal state must satisfy the KMS condition, which encodes the fluctuation-dissipation relation and identifies the thermal density matrix uniquely. Bootstrapping the thermal state means finding the smallest feasible region consistent with all these constraints, so that any observable within this region is bounded.

**Key intuition.** The bootstrap variables are thermal single-trace expectation values $\langle \operatorname{Tr}(\mathcal{O}_i^\dagger \mathcal{O}_j) \rangle_\beta$, organized into a moment matrix $\mathcal{M}_{ij}$. The positivity of the quantum state forces $\mathcal{M} \succeq 0$ (an SDP constraint). The KMS condition — which says the state is thermal — adds a nonlinear constraint linking $\mathcal{M}$ to its time-shifted version via a relative entropy inequality. Conventional linear SDP replaces $\log$ with a rational approximation so everything becomes an SDP; QICS handles $\log$ exactly through iterative Newton linearizations inside an interior-point iteration.

**Logical flow.** (1) Choose a truncation level $L$ (maximum operator product length). (2) Assemble the bootstrap variables: all single-trace expectation values of products up to length $L/2$. (3) Impose symmetry constraints (parity, time-reversal, cyclicity, large-$N$ factorization, commutation relations, stationarity) to reduce the variable count. (4) Solve the conic optimization minimizing/maximizing the thermal energy subject to $\mathcal{M} \succeq 0$ and the KMS cone constraint. (5) Compare the resulting bounds at low temperature to the analytic long-string effective theory to extract long-string parameters.

**Regime.** This analysis applies in the strict large-$N$ limit (large-$N$ factorization is exact), at finite inverse temperature $\beta$, for the ungauged theory. The long-string comparison is valid only at low temperature (small $e^{-\beta\Delta_1}$). The QICS approach is limited by double-precision arithmetic; for very large $L$ or multi-matrix models, arbitrary-precision solvers would be needed.

## Key Results

1. **One-matrix bootstrap bounds (L=12, g=2):** QICS produces energy upper and lower bounds at system size $L=12$ that are strictly tighter than those from Cho et al. at $L=10$ and where MOSEK (linear SDP) becomes unstable (Figure 3 of Adams 2025).

2. **Long-string ground state energy extraction:** Fitting the $L=12$ QICS bounds at low temperature to the 2-loop long-string expansion (Eq. K.14) yields $e_0 = 0.865457750210 \pm 3\times10^{-7}$ vs. analytic $0.8654577$ (Table 1 of Adams 2025, low-T fit).

3. **First long-string excited energy:** $\Delta_1 = 2.1283360 \pm 2\times10^{-4}$ vs. analytic $2.1281936$ (Table 1 of Adams 2025, low-T fit); bootstrap value within $0.001\%$ of analytic.

4. **First coupling coefficient $h_{1111}$:** $h_{1111} = 0.32731 \pm 7\times10^{-2}$ vs. numerical $0.3278$ (Table 1 of Adams 2025, low-T fit). This is described as the first estimation of $h_{1111}$ from symmetry and self-consistency alone.

5. **QICS vs. MOSEK agreement:** At $L=8$, QICS and MOSEK (with $(m,k)=(3,3)$ log relaxation) agree within numerical tolerance; at $L=10$, MOSEK requires relaxed tolerance $10^{-7}$ to converge at most temperatures, while QICS converges at default $10^{-8}$ (Section 4.1 of Adams 2025).

6. **Two-matrix bootstrap with complex operators:** Switching to complex operators (Eq. K.4) and imposing $U(1)$ charge conservation reduces the two-matrix variable count from 25 to 12 at $L=4$ and from 220 to 81 at $L=6$, enabling bounds (noisy) at that truncation level at coupling $g=0.1$ (Section 4.2 and figure caption "Thermal energy bounds for g=0.1" of Adams 2025).

7. **KMS condition as operator relative entropy cone:** The thermal (KMS) condition is exactly equivalent (Araki-Sewell, Fawzi et al.) to the conic inequality $\beta C \succeq A^{1/2} \log(A^{1/2}B^{-1}A^{1/2})A^{1/2}$, eq. K.7 (Section 3 of Adams 2025).

## Equations

**(K.1)** One-matrix anharmonic oscillator Hamiltonian:
$$H = \operatorname{Tr}\!\left(\tfrac{1}{2}P^2 + \tfrac{1}{2}X^2 + \tfrac{g}{N}X^4\right)$$
Context: Large-$N$ 't Hooft limit; $X, P$ are traceless $N\times N$ Hermitian matrices; $g$ is the quartic coupling. Adams eq. (1) (source line 52).
Why/How: The $g/N$ coupling is the 't Hooft rescaling that ensures a nontrivial large-$N$ limit. After rescaling $X,P$ by $1/\sqrt{N}$ and using $\langle\operatorname{Tr}\mathcal{O}\rangle \sim N$, the $1/N$ in front of $X^4$ drops.

**(K.2)** Two-matrix anharmonic oscillator Hamiltonian:
$$H = \operatorname{Tr}\!\left(\tfrac{1}{2}(P_1^2+P_2^2) + \tfrac{1}{2}(X_1^2+X_2^2) - \tfrac{g}{N}[X_1,X_2]^2\right)$$
Context: Two-matrix model with mass term included. Adams eq. (5) (source line 88). Motivated by the bosonic sector of BFSS truncated to two matrices.
Why/How: Because $[X_1,X_2]$ is anti-Hermitian for Hermitian $X_i$, we have $[X_1,X_2]^2 \leq 0$ as an operator (i.e., $-[X_1,X_2]^2 = [X_1,X_2]^\dagger[X_1,X_2] \geq 0$), so the term $-g/N[X_1,X_2]^2 \geq 0$ contributes positively to $H$ and raises the energy. Inclusion of the mass term $\frac{1}{2}(X_1^2+X_2^2)$ is a simplification relative to the massless BFSS truncation.

**(K.3)** Large-$N$ commutation relation:
$$\frac{1}{N}[X_{ab}, P_{cd}] = \frac{i}{N}\delta_{ad}\delta_{bc} + \mathcal{O}(1/N^2)$$
Context: At leading order in $1/N$; components expand as $X_{ab} = X^A T^A_{ab}$ with traceless Hermitian $SU(N)$ generators $T^A_{ab}$ satisfying $T^A_{ab}T^A_{cd} = \delta_{ad}\delta_{bc} - \frac{1}{N}\delta_{ab}\delta_{cd}$. Adams eq. (4) (source line 64).
Why/How: This is the canonical commutation relation $[X^A, P^B] = i\delta^{AB}$ rewritten in matrix components. At large $N$, the $1/N^2$ correction drops.

**(K.4)** Complex operators for two-matrix model:
$$P = \tfrac{1}{\sqrt{2}}(P_1 + iP_2),\quad \bar{P} = \tfrac{1}{\sqrt{2}}(P_1 - iP_2),\quad X = \tfrac{1}{\sqrt{2}}(X_1 + iX_2),\quad \bar{X} = \tfrac{1}{\sqrt{2}}(X_1 - iX_2)$$
Context: Adams eq. (6) (source line 94). In this basis the two-matrix Hamiltonian becomes $H = \operatorname{Tr}(P\bar{P} + X\bar{X} + \frac{g}{N}[X,\bar{X}]^2)$, Adams eq. (7) (source line 99).
Why/How: This diagonalizes the $SO(2)$ symmetry into a $U(1)$ charge, enabling $U(1)$ charge conservation as an additional constraint that substantially reduces the variable count. The two forms of the Hamiltonian (K.2 and the complex-basis form) are equal because of the identity:
$$[X,\bar{X}] = \tfrac{1}{2}[X_1+iX_2, X_1-iX_2] = -i[X_1,X_2] \quad\Rightarrow\quad [X,\bar{X}]^2 = -[X_1,X_2]^2$$
(derivation: $[X_1+iX_2, X_1-iX_2] = -i[X_1,X_2]+i[X_2,X_1] = -2i[X_1,X_2]$). Substituting into the complex Hamiltonian:
$\operatorname{Tr}(P\bar{P}+X\bar{X}+\tfrac{g}{N}[X,\bar{X}]^2) = \operatorname{Tr}(\tfrac{P_1^2+P_2^2}{2}+\tfrac{X_1^2+X_2^2}{2}-\tfrac{g}{N}[X_1,X_2]^2) = $ K.2.
(The cross-term from $\operatorname{Tr}(X\bar{X})$ is $-\frac{i}{2}\operatorname{Tr}([X_1,X_2]) = +\frac{i}{2}\operatorname{Tr}([X_2,X_1])$, which vanishes since the trace of any commutator is zero. Similarly, $\operatorname{Tr}(P\bar{P}) = \operatorname{Tr}(\tfrac{P_1^2+P_2^2}{2}) - \tfrac{i}{2}\operatorname{Tr}([P_1,P_2])$, where the commutator term also vanishes by cyclicity of the trace.)

**(K.5)** Moment matrix semidefiniteness:
$$\mathcal{M}_{ij} = \langle \operatorname{Tr}(\mathcal{O}_i^\dagger \mathcal{O}_j) \rangle_\beta \succeq 0$$
Context: The moment matrix of single-trace operators $\{\mathcal{O}_i\}$ built from products up to length $L/2$. Definition of $\mathcal{M}_{ij}$ appears in the bullet-point constraint list (source line 72); the semidefiniteness condition $\mathcal{M} \succeq 0$ is Adams eq. (11) (source line 123).
Why/How: $\mathcal{M}_{ij} = \langle\psi|\mathcal{O}_i^\dagger\mathcal{O}_j|\psi\rangle$ in any state; positivity follows from the inner product being positive definite.

**(K.6)** KMS (thermal) condition matrices. Define:
$$A_{ij} = \frac{1}{N^2}\!\left(\langle\operatorname{Tr}(\mathcal{O}_i^\dagger\mathcal{O}_j)\rangle_\beta - \tfrac{1}{N}\langle\operatorname{Tr}(\mathcal{O}_i^\dagger)\rangle_\beta\langle\operatorname{Tr}(\mathcal{O}_j)\rangle_\beta\right)$$
$$B_{ij} = \frac{1}{N^2}\!\left(\langle\operatorname{Tr}(\mathcal{O}_j\mathcal{O}_i^\dagger)\rangle_\beta - \tfrac{1}{N}\langle\operatorname{Tr}(\mathcal{O}_j)\rangle_\beta\langle\operatorname{Tr}(\mathcal{O}_i^\dagger)\rangle_\beta\right)$$
$$C_{ij} = \frac{1}{N^2}\langle\operatorname{Tr}(\mathcal{O}_i^\dagger[H,\mathcal{O}_j])\rangle_\beta$$
Context: Adams eqs. (13), (14), (15) (source lines 131, 134, 138). $\mathcal{O}_i$ tuples up to length $(L-4)/2$. Note: in the source, eq. (12) (the KMS cone, K.7 below) appears before eqs. (13)–(15); the doc presents K.6 before K.7 to follow the logical order (definitions precede the inequality that uses them).
Why/How: $A$ and $B$ are the Tomita–Takesaki modular matrices at the large-$N$ level; $C$ is the Hamiltonian commutator matrix. The KMS condition is equivalent (Araki-Sewell 1977; Fawzi et al. 2024) to the operator relative entropy inequality below.

**(K.7)** Operator relative entropy cone (KMS constraint):
$$\beta C \succeq A^{1/2}\log\!\left(A^{1/2}B^{-1}A^{1/2}\right)A^{1/2}$$
Context: Exact encoding of KMS condition as a conic inequality. Adams eq. (12) (source line 127). Equivalent to the Kubo–Martin–Schwinger periodicity condition. This is the nonlinear cone that QICS handles directly.
Why/How: The log makes this a quantum relative entropy cone constraint ($D(A\|B) \leq \beta C$ in matrix form). This is handled natively by QICS via the Skajaa–Ye interior-point algorithm; linear SDP methods must approximate $\log$.

**(K.8)** Log approximation (linear SDP approach, for comparison):
$$\log(x) \approx r_{m,k}(x) := 2^k r_m\!\left(x^{1/2^k}\right), \qquad r_m(x) = \sum_{j=1}^m w_j f_{t_j}(x), \qquad f_t(x) = \frac{x-1}{t(x-1)+1}$$
Context: Adams eqs. (16), (17) (source lines 142, 147–148). The Gauss–Radau exactness condition (eq. (18), source line 153) requires $\int_0^1 p(t)\,dt = \sum_{j=1}^m w_j p(t_j)$ for polynomials of degree $\leq 2m-2$, with $t_1=0.6$. Used by Cho et al. with $(m,k)=(3,3)$ and MOSEK.
Why/How: $r_{m,k}$ provides a rigorous upper bound on $\log x$ that tightens with increasing $(m,k)$. Replacing $\log$ with $r_{m,k}$ converts the conic constraint into an SDP, but introduces both approximation error and additional SDP variables/constraints that grow with $m,k$.

**(K.9)** Long-string semiclassical action integral:
$$J(e) = \frac{1}{\pi}\int_{\lambda_-(e)}^{\lambda_+(e)} d\lambda\,\sqrt{2(e - v(\lambda))}, \qquad v(\lambda) = \frac{\lambda^2}{2} + g\lambda^4$$
Context: Adams eq. (19) for $J(e)$ (source line 195); eq. (20) for $v(\lambda)$ (source line 200); eq. (21) for $\rho(\lambda)$ (source line 204): $\rho(\lambda) = \frac{1}{\pi}\sqrt{2(e_f - v(\lambda))}$. $\lambda_\pm(e)$ are the turning points of $v$. Fermi energy $e_f$ satisfies $J(e_f) = 1$; ground-state eigenvalue density $\rho$ uses $e_f$.
Why/How: This is the semiclassical (WKB) quantization for the effective one-dimensional problem for each matrix eigenvalue. At large $N$ the eigenvalue distribution is a semicircle generalization.

**(K.10)** Long-string integral eigenvalue equation:
$$\int_{\lambda_-(e)}^{\lambda_+(e)}\!d\lambda'\,\rho(\lambda')\frac{w_n(\lambda)-w_n(\lambda')}{(\lambda-\lambda')^2} = \Delta_n\,w_n(\lambda)$$
Context: Adams eq. (22) (source line 208); from Cho et al. and Marchesini–Onofri. Integration limits are $\lambda_\pm(e)$ (generic Fermi energy, in practice $e = e_f$). Eigenvectors $w_n$ satisfy orthogonality $\int d\lambda\,\rho(\lambda)w_n(\lambda)=0$ and normalization $\int d\lambda\,\rho(\lambda)|w_n(\lambda)|^2=1$. $\Delta_n$ are long-string excitation energies relative to the ground state.
Why/How: This singular integral eigenvalue equation (Hilbert-transform type) determines the long-string spectrum in the adjoint sector at large $N$.

**(K.11)** Long-string thermal partition function (2-loop planar):
$$\frac{-\log Z(\beta)}{N^2} = \sum_n \log(1-e^{-\beta\Delta_n}) + \beta\sum_{j,k}\frac{h_{jkjk}}{(e^{\beta\Delta_j}-1)(e^{\beta\Delta_k}-1)} + \mathcal{O}(h^2)$$
Context: Adams eq. (23) (source line 217, label `partitionfunc`). 2-loop order in planar limit; from Cho et al. Note: in the paper this equation precedes the coupling coefficient definition K.12.
Why/How: First term is the free boson sum; second term captures the leading long-string interaction at finite temperature. Only diagonal couplings $h_{jkjk}$ enter at this order.

**(K.12)** Long-string coupling coefficients:
$$h_{abcd} = -\int_{\lambda_-(e)}^{\lambda_+(e)}\!\!d\lambda\int_{\lambda_-(e)}^{\lambda_+(e)}\!\!d\lambda'\,\rho(\lambda)\rho(\lambda')\frac{w_c^*(\lambda)w_d^*(\lambda')(w_a(\lambda)-w_a(\lambda'))(w_b(\lambda)-w_b(\lambda'))}{(\lambda-\lambda')^2}$$
Context: Adams eq. (24) (source line 222, label `habcd`). Integration limits are written as $\lambda_\pm(e)$ in the source (generic notation); in practice $e = e_f$ (the Fermi energy at which $J(e_f)=1$). These are the two-loop planar interaction coefficients in the long-string effective theory.
Why/How: The coupling enters the thermal partition function at second order in the Bose–Einstein occupation factors.

**(K.13)** Low-temperature energy expansion (one-matrix, first order):
$$\frac{E_{L.T.}^{(1)}}{N^2} \coloneqq e_0 + \Delta_1\,e^{-\beta\Delta_1}$$
Context: Adams eq. (29) (source line 300). Leading term in the low-$T$ expansion $e^{-\beta\Delta_1} \ll 1$. Source uses $\coloneqq$ (definitional assignment) and no explicit $(\beta)$ argument on the LHS. The general leading form including the $\mathcal{O}(e^{-2\beta\Delta_1},e^{-\beta\Delta_2})$ correction is Adams eq. (28) (source line 295), which does carry $(\beta)$ explicitly.
Why/How: $e_0$ is the ground state energy per unit $N^2$; $\Delta_1$ is the first long-string excitation energy. At low $T$, higher excitations are exponentially suppressed.

**(K.14)** Low-temperature energy expansion (second order):
$$\frac{E_{L.T.}^{(2)}}{N^2} \coloneqq e_0 + \Delta_1\,e^{-\beta\Delta_1} + \Delta_2\,e^{-\beta\Delta_2} + [\Delta_1 + h_{1111}(1-2\beta\Delta_1)]e^{-2\beta\Delta_1}$$
Context: Adams eq. (30) (source line 304). Includes the two-loop interaction term $h_{1111}$. Source uses $\coloneqq$ (definitional assignment) and no explicit $(\beta)$ argument on the LHS; both restored here to match source notation.
Why/How: The coefficient $[\Delta_1 + h_{1111}(1-2\beta\Delta_1)]$ encodes both the second harmonic of the first excitation and the interaction correction from $h_{1111}$.

**(K.15)** Discretized eigenvalue equation matrix (Nyström method):
$$M_{ij} = \begin{cases} \dfrac{\sqrt{\omega_i^{\text{quad}}\omega_j^{\text{quad}}\rho(\lambda_i)\rho(\lambda_j)}}{(\lambda_i-\lambda_j)^2}, & i\neq j\\ 0, & i=j\end{cases}$$
Context: Adams eq. (27) (source line 253–258, label `finaleigenvalueequation`). Quadrature nodes $\lambda_i$ and weights $\omega_i^{\text{quad}}$ from Gaussian quadrature; diagonal regularization (principal-value limit). This follows from rescaling $\tilde{w}_i := \sqrt{\omega_i^{\text{quad}}\rho(\lambda_i)}\,w_n(\lambda_i)$ (Adams eq. (26), source line 243).
Why/How: The diagonal $M_{ii}=0$ regularizes the principal-value singularity. The matrix $M$ is real and symmetric; its eigenvalues converge to the continuum $\Delta_n$ as $Q$ increases.

**(K.16)** Key numerical values for $g=2$ long-string spectrum (Marchesini–Onofri 1978):
$$e_0 = 0.8654577,\quad \Delta_1 = 2.1281936,\quad \Delta_2 = 4.6201131,\quad \Delta_3 = 7.0716122,\quad \Delta_4 = 9.5258038$$
Context: Adams cites Marchesini & Onofri (1978) for these values; listed inline in Adams Section 4.1 (source line 213).
Why/How: These are benchmark values for validating bootstrap bounds and fitting extracted long-string parameters.

**(K.17)** Long-string coupling coefficients numerically computed (Nyström, $Q=1200$, $g=2$):
$$h_{1111} \approx 0.3278,\quad h_{1212}=h_{2121}\approx 0.6207,\quad h_{1313}=h_{3131}\approx 0.5921,\quad h_{2222}\approx 1.119$$
Context: Adams Table 1 ($Q=1200$ Nyström quadrature row, source lines 286–287). Exact values: $h_{1111}=0.327784$, $h_{1212}=0.620731$, $h_{1313}=0.592072$, $h_{2222}=1.11909$; also $\Delta_1=2.12573$ at $Q=1200$. Note: $e_0$ and $\Delta_n$ in K.16 are from Marchesini–Onofri (1978) analytic/integral methods; the $h_{abcd}$ values here are from the Adams Nyström numerical computation (no analytic formula exists for $h_{abcd}$). Both appear under the heading "Analytic/numerical" in Adams Table 1, but they are qualitatively different benchmarks.
Why/How: Converged Nyström values at $Q=1200$ quadrature points; $\Delta_1$ converges to $2.12573$ at $Q=1200$ (vs. Marchesini analytic $2.1281936$ — residual $0.12\%$ Nyström discretization error; see Trap 1 below).

## Conventions

- **Large-$N$ scaling**: $X,P$ are $N\times N$ Hermitian matrices; each $\langle\operatorname{Tr}(\cdot)\rangle \sim \mathcal{O}(N)$. All energy quantities are expressed per unit $N^2$ (i.e., $E/N^2$, $e_0$, $\Delta_n$, $h_{abcd}$ are all $\mathcal{O}(1)$ in the large-$N$ limit).
- **Operator length $L$**: Maximum length of an operator product; bootstrap variables are products of $X,P$ up to length $L/2$. KMS constraint uses operators up to length $(L-4)/2$.
- **Coupling**: The quartic coupling is $g$ (not $\lambda$), with the convention $H = \operatorname{Tr}(\ldots + g/N\, X^4)$ (one-matrix) or $H = \operatorname{Tr}(\ldots - g/N\, [X_1,X_2]^2)$ (two-matrix). The numerical results reported in the paper use $g=2$ for the one-matrix bootstrap and $g=0.1$ for the two-matrix bootstrap (confirmed from figure captions in Adams 2025).
- **$U(1)$ charge**: For the complex two-matrix basis, $U(1)$ charge of a monomial = (number of **barred** operators) $-$ (number of **unbarred** operators) (Adams Section 2.2: "the $U(1)$ charge of a term is the difference between the number of barred and unbarred operators"). Zero-charge observables are the only nonzero ones by symmetry. Caution: this convention assigns positive charge to monomials with more $\bar{X},\bar{P}$ factors, which is opposite to some other conventions where $X$ carries positive charge.
- **No metric signature**: MQM is Euclidean (no Lorentzian metric); inverse temperature $\beta > 0$.
- **Comparison with K-001 (Lin 2023)**: Lin bootstraps at arbitrary fixed energy $E$ (microcanonical / energy-eigenstate constraint $\langle H\mathcal{O}_i\rangle = E\langle\mathcal{O}_i\rangle$, valid for any $E\geq 0$) using pure SDP; Adams bootstraps at finite temperature $T>0$ (canonical / thermal KMS constraint) using conic optimization. Both approaches use a moment matrix $\mathcal{M}\succeq 0$ and single-trace variables, but the supplemental constraints differ: Lin imposes $\langle[H,\mathcal{O}_i]\rangle=0$ (stationarity in an energy eigenstate), while Adams imposes the operator relative entropy cone K.7 (KMS condition for a thermal state).

## Derivation Sketches

**KMS condition → operator relative entropy cone (Eq. K.7):** The KMS condition for a thermal state $\rho_\beta = e^{-\beta H}/Z$ states that for any two operators $A,B$: $\langle AB \rangle_\beta = \langle B e^{\beta H} A e^{-\beta H}\rangle_\beta$, i.e., time-translation by $-i\beta$ implements a modular automorphism. At the level of the moment matrices $A,B$ (defined in Eq. K.6), this KMS periodicity is equivalent (by the Petz recovery map / Araki–Sewell theorem) to the operator relative entropy inequality $D(A\|B) \leq \beta C$ in the sense of eq. (K.7). Araki–Sewell (1977) establishes this equivalence for $C^*$ algebras; Fawzi et al. (2024) gives the explicit conic form used in Adams.

**Log approximation (Eq. K.8):** The Gauss–Radau quadrature approximation $r_m(x) = \sum_j w_j f_{t_j}(x)$ with $f_t(x) = (x-1)/(t(x-1)+1)$ approximates $\log x$ from above (upper bound). Composing $k$ half-steps $r_{m,k}(x) = 2^k r_m(x^{1/2^k})$ improves the bound by exploiting the concavity of $\log$. The rigorous upper bound property means: replacing $\log$ with $r_{m,k}$ in eq. (K.7) gives a relaxed (weaker) conic constraint, i.e., the SDP-feasible region is a superset of the exact conic feasible region. Any energy bound from the relaxed SDP is therefore an outer bound.

**Nyström discretization (Eq. K.15):** The integral eigenvalue equation (K.10) is a Fredholm equation of the second kind with a Cauchy-type singular kernel $(\lambda-\lambda')^{-2}$. Gaussian quadrature discretizes the integral; the principal-value singularity is regularized by setting $M_{ii}=0$, corresponding to the cancellation $(w_n(\lambda)-w_n(\lambda'))/(\lambda-\lambda')^2 \to 0$ as $\lambda'\to\lambda$ for smooth $w_n$. The resulting matrix $M$ is real symmetric; standard dense eigensolvers find $\Delta_n$.

## Connections

- **K-001 (Lin 2023)**: Lin uses pure SDP with ground-state energy constraints; Adams uses conic optimization with the KMS thermal constraint. Both target large-$N$ MQM; Lin targets BFSS, Adams targets anharmonic oscillators. The constraint structure (moment matrix + symmetry reduction) is identical in spirit; the key difference is ground-state vs. thermal and SDP vs. conic.
- **Cho et al. ([arXiv ID TBD; bib key: cho2025thermalbootstrapmatrixquantum])**: Direct predecessor; Adams uses the same bootstrap framework but replaces the linear SDP log-relaxation with QICS. The $(m,k)=(3,3)$ MOSEK bounds from Cho et al. are the baseline that Adams improves upon.
- **BFSS project**: The two-matrix model truncation (Eq. K.2) is a step toward bootstrapping the full 9-matrix BFSS model. The long-string effective theory (Eqs. K.9–K.14) is specifically the low-temperature description of the BFSS ungauged sector, and the extracted $e_0$, $\Delta_1$, $h_{1111}$ are physically meaningful BFSS-related quantities.
- **Used by**: Any phase involving thermal bootstrap bounds or long-string parameter extraction for the one/two-matrix models.

## Open Questions

- Whether the two-matrix bootstrap can reach $L=8$ or beyond with an arbitrary-precision conic solver, or whether a fundamentally different approach is needed.
- Whether the full 9-matrix BFSS model thermal bootstrap is tractable with QICS at any system size.
- The coupling coefficient extraction has large relative uncertainty for $h_{1111}$ (full-graph fit gives $h_{1111}=0.49983\pm0.04$, inconsistent with the low-$T$ fit value $0.32731\pm0.07$ and the numerical $0.3278$); the discrepancy between the two fitting domains is not explained.
- Whether the long-string effective theory description can be used to bound higher coupling coefficients $h_{abcd}$ with $a\neq b$ via bootstrap.
- Connection to the Skajaa–Ye algorithm convergence guarantees: what system-size limits follow from double precision?

## Traps and Subtleties

1. **Nyström convergence vs. Marchesini values**: Adams Table 1 shows $\Delta_1 = 2.12573$ at $Q=1200$ quadrature, but the Marchesini analytic value is $2.1281936$. This is a residual $0.12\%$ discrepancy. The abstract claims bootstrap $\Delta_1$ is within $0.001\%$ of the physical value — this refers to the bootstrap-extracted $\Delta_1=2.1283360\pm2\times10^{-4}$ vs. Marchesini $2.1281936$, not the Nyström computation. Do NOT confuse the Nyström numerical computation of $\Delta_1$ (converging slowly in $Q$) with the analytic Marchesini value or the bootstrap-extracted value.

2. **Two fitting regimes for $h_{1111}$**: The low-$T$ fit gives $h_{1111}=0.32731\pm0.07$, consistent with numerical $0.3278$; the full-graph fit gives $h_{1111}=0.49983\pm0.04$, inconsistent. Adams does not resolve this discrepancy. Users should treat the full-graph $h_{1111}$ value with caution.

3. **KMS constraint on operator subspace of length $(L-4)/2$, not $L/2$**: The matrices $A,B,C$ in Eq. K.6 are built from operators up to length $(L-4)/2$, not $L/2$. This is a smaller subspace than the moment matrix $\mathcal{M}$. Using length $L/2$ for the KMS matrices would be an error.

4. **$1/N$ normalization in moment matrices**: $A_{ij}$ and $B_{ij}$ include the $-\frac{1}{N}\langle\operatorname{Tr}(\mathcal{O}_i^\dagger)\rangle\langle\operatorname{Tr}(\mathcal{O}_j)\rangle$ subtraction (connected part) and a $1/N^2$ prefactor. The $\mathcal{M}_{ij} = \langle\operatorname{Tr}(\mathcal{O}_i^\dagger\mathcal{O}_j)\rangle$ in Eq. K.5 does NOT have this prefactor. Confusing $\mathcal{M}$ with $A$ or $B$ introduces factor-of-$N^2$ errors.

5. **Log approximation is an upper bound on $\log$, giving a weaker (outer) feasibility region**: $r_{m,k}(x) \geq \log x$ always. Replacing the exact cone with the SDP approximation makes the feasibility region larger (less constrained), so SDP bounds are valid outer bounds but not as tight as QICS bounds. This is not an error but a deliberate approximation — important when comparing MOSEK vs. QICS results.

6. **Diagonal regularization in Nyström ($M_{ii}=0$)**: Setting diagonal to zero is NOT a typo or approximation error — it is the correct principal-value regularization for the Cauchy-singular kernel. Attempting to compute $M_{ii}$ using the formula with $i=j$ would give $\infty/0$.

7. **Two-matrix Hamiltonian sign**: The commutator term in K.2 is $-g/N[X_1,X_2]^2$. Since $[X_1,X_2]$ is anti-Hermitian for Hermitian $X_i$, we have $[X_1,X_2]^2 = -[X_1,X_2]^\dagger[X_1,X_2] \leq 0$ as an operator, so $-[X_1,X_2]^2 = [X_1,X_2]^\dagger[X_1,X_2] \geq 0$ and the term contributes positively to $\operatorname{Tr}(H)$ (raises the energy). In the complex basis (K.4), the corresponding term is $+g/N[X,\bar{X}]^2$, which is consistent because $[X,\bar{X}]^2 = -[X_1,X_2]^2$ (see derivation in K.4). Do not confuse with the BFSS Hamiltonian in K-001 (Lin 2023), where the bosonic potential is $V = -\frac{1}{4g^2}\operatorname{Tr}[X_I,X_J]^2 \geq 0$ — same positive-definite structure, but different normalization and matrix content (9 matrices, dimensionful coupling $g_{YM}$).

8. **Integration limits in K.12 vs. source notation**: Adams eq. (24) writes the integration limits as $\lambda_\pm(e)$ (generic notation inherited from eqs. (19)–(22)), not $\lambda_\pm(e_f)$ explicitly. In the context of evaluating $h_{abcd}$, $e = e_f$ is always implied. The source eqs. (19)–(22) consistently use the generic $e$ notation; $e_f$ enters only through the Fermi-energy boundary condition $J(e_f)=1$ and the definition of $\rho(\lambda)$ in eq. (21).
