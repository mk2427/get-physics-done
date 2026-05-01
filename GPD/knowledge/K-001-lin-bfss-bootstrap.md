---
kdoc_id: K-001-lin-bfss-bootstrap
status: Stable
topic: "Bootstrap bounds on BFSS matrix theory / D0-brane quantum mechanics"
cluster: "bfss-bootstrap"
sources:
  - "arXiv:2302.04416 [hep-th] — H. W. Lin, 'Bootstrap bounds on D0-brane quantum mechanics'"
created: 2026-04-27
last_reviewed: 2026-04-28
review_rounds: 4
superseded_by: null
eqn_ref_schema_version: 1
assertion_schema_version: 1
layout: single
---

# Knowledge: Bootstrap Bounds on BFSS Matrix Theory (Lin 2023)

## Overview

This document covers the bootstrap analysis of the BFSS matrix theory (D0-brane quantum mechanics) carried out by H. W. Lin in arXiv:2302.04416. The paper derives the first non-trivial analytic lower bound on $\langle \mathrm{tr}\, \tilde{X}^2 \rangle$ (where $\tilde{X} = \lambda^{-1/3} X$ is the dimensionless matrix), extending Polchinski's 1999 virial bound to finite energies and strengthening it by incorporating fermionic constraints. The bootstrap proceeds by (1) applying the virial theorem via $\langle [H, O] \rangle = 0$ in approximate energy eigenstates, (2) assembling positivity-constraint matrices from single-trace correlators, and (3) solving the resulting semidefinite feasibility problems analytically. The best lower bound on $\langle \mathrm{tr}\, \tilde{X}^2 \rangle$ is within a factor of $\sim 2$ of existing Monte Carlo results, providing a proof-of-principle that the BFSS bootstrap is tractable.

## Key Results

1. **Canonical commutation relations** for the component fields: eq. (K.1), TeX label `canonical`. These are the starting point for all bootstrap commutator evaluations.

2. **BFSS Hamiltonian** in the conventions of the paper: eq. (K.2), TeX label `ham`. This is the single most important equation — all bootstrap constraints derive from it.

3. **Virial theorem** (two independent equations): eqs. (K.5)–(K.6), TeX label `virial_idea`. Applying $\langle [H, \mathrm{Tr}\, XP] \rangle = 0$ gives these two equations, which link $\langle K \rangle$, $\langle V \rangle$, $\langle F \rangle$, and $E$.

4. **Polchinski / uncertainty bound** on $\langle \mathrm{Tr}\, X^4 \rangle$ as a function of energy: eq. (K.9), TeX label `Polchinski`. At $E=0$ this reproduces the Polchinski 1999 ground-state estimate $\Delta X \sim \lambda^{1/3}$.

5. **Positivity matrix $\mathcal{M}_2$** (the central $3 \times 3$ matrix combining bosonic and fermionic correlators): eq. (K.12), TeX label `Cm2`. This is the key new object in the paper; demanding $\mathcal{M}_2 \succeq 0$ yields the bound on $\langle \mathrm{Tr}\, X^2 \rangle$.

6. **Fermionic operator bound**: eq. (K.13), TeX label `fermionBd`. The Majorana structure forces $\frac{1}{9} \langle \mathrm{Tr}\, O_I O_I \rangle \le 64 N^3$, which closes the SDP.

7. **Lower bound on $\langle \mathrm{tr}\, \tilde{X}^2 \rangle$**: eqs. (K.14)–(K.15), TeX labels `firstLine` and `secondLine`. At $E=0$ this gives $\langle \mathrm{tr}\, \tilde{X}^2 \rangle \ge 3/16$.

8. **Improved lower bound on $\langle \mathrm{tr}\, \tilde{X}^4 \rangle$** incorporating fermionic constraints: eq. (K.17), TeX label `bigEconstr`. At $E=0$ this gives $\langle \mathrm{tr}\, \tilde{X}^4 \rangle \ge ((7 - 4\sqrt{3})/256)^{1/3} \approx 0.06546$, improving the Polchinski value of $1/16 = 0.0625$.

9. **Two-sided bound on $\gamma$** (the commutator-to-moment ratio): eq. (K.16), TeX label `gammaBd`. This is the only quantity for which the paper achieves a non-trivial upper bound.

10. **Black hole thermodynamics** in the gravity dual: eq. (K.3), TeX label `thermo`. The characteristic energy scale $E/N^2 \sim \lambda^{1/3}$ where the bound transitions corresponds exactly to the breakdown of the supergravity approximation.

11. **Fermionic Casimir identities** underpinning the SDP bound: eqs. (K.18)–(K.22), TeX labels `ttCas`, `psi2`, `psi4`, `posAB`, `MAB`, Appendix C. These derive the explicit numerical bounds that enter (K.13) and close the SDP for $\langle\mathrm{tr}\,\tilde{X}^2\rangle$.

12. **Stronger SO(9) bound on $\langle\mathrm{tr}\,X^4\rangle$**: eq. (K.23), TeX label `strongerSO9`, Appendix D. Derived from the full positivity matrix over $\{1, X^I, X^I X^J\}$ under SO(9) invariance; does not improve the main bounds of Figure 1 but is a rigorous consequence of the positivity constraints.

## Equations

(K.1) Canonical (anti-)commutation relations for the component fields:
$$\{ \psi_\alpha^A, \psi_\beta^B \} = \delta^{AB} \delta_{\alpha\beta}, \qquad [X_I^A, P_J^B] = i\, \delta^{AB} \delta_{IJ}$$
Context: TeX label `canonical`, §2.1. Here $X_I^A$ are the real non-relativistic particle degrees of freedom (not the matrix-valued $X_I$), and $\psi_\alpha^A$ are Majorana fermions. Indices $A, B$ run over the $N^2 - 1$ generators of $\mathrm{su}(N)$.

(K.2) BFSS Hamiltonian:
$$H = \frac{1}{2} \operatorname{Tr}\!\left( g^2 P_I^2 - \frac{1}{2g^2} [X_I, X_J]^2 - \psi_\alpha \gamma^I_{\alpha\beta} [X_I, \psi_\beta] \right)$$
Context: TeX label `ham`, §2.1. Implicit sum over $I, J = 1, \ldots, 9$ and spinor indices $\alpha, \beta = 1, \ldots, 16$. All matrices are $N \times N$ Hermitian and traceless. Units: $X$ has units of energy; $g^2$ has units of $E^3$. The Hamiltonian splits as $H = K + V + F$ where
$$K = \frac{g^2}{2} \mathrm{Tr}\, P_I^2, \quad V = -\frac{1}{4g^2} \mathrm{Tr}\, [X_I, X_J]^2, \quad F = -\frac{1}{2} \mathrm{Tr}\, \psi_\alpha \gamma^I_{\alpha\beta} [X_I, \psi_\beta].$$

(K.3) Black hole thermodynamics (gravity dual, 't Hooft limit):
$$\frac{E}{N^2} = \lambda^{1/3} \frac{9}{14} 4^{13/5} 15^{2/5} \!\left(\frac{\pi}{7}\right)^{14/5}\!\! \left(\frac{T}{\lambda^{1/3}}\right)^{14/5}$$
Context: TeX label `thermo`, §2.1. Valid when $T^3 \ll \lambda$ (gravity regime). Derived from Bekenstein-Hawking entropy in Einstein frame with $16\pi G_N = (2\pi)^7 (\alpha')^4$. Used throughout to convert between the energy scale $E/N^2 \sim \lambda^{1/3}$ and temperature $T \sim \lambda^{1/3}$.

(K.4) Uncertainty-principle positivity matrix (Round 1):
$$\mathcal{M} = \begin{pmatrix} \langle \mathrm{Tr}\, X^2 \rangle & \langle \mathrm{Tr}\, XP \rangle \\ \langle \mathrm{Tr}\, PX \rangle & \langle \mathrm{Tr}\, P^2 \rangle \end{pmatrix} \succeq 0 \quad \Rightarrow \quad \sum_I \langle \mathrm{Tr}\, X^2 \rangle \langle \mathrm{Tr}(P^I P_I) \rangle \ge \frac{9}{4} N^4$$
Context: TeX label `uncertain`, §2.2. The off-diagonal entries are fixed by the constraint $\langle [H, \mathrm{Tr}\, X^2] \rangle = 0$, which gives $\langle \mathrm{Tr}\, XP \rangle = -\langle \mathrm{Tr}\, PX \rangle = iN^2/2$. The factor $9$ comes from summing over all 9 bosonic matrices in an SO(9)-invariant state.

(K.5) Virial theorem — equation 1 (from $\langle [H, \mathrm{Tr}\, XP] \rangle = 0$):
$$-2\langle K \rangle + 4\langle V \rangle + \langle F \rangle = 0$$
Context: TeX label `virial_idea`, §2.2. This is the standard matrix-model virial theorem. The coefficients $-2$, $4$, $1$ are derived by direct computation of $\langle[H, \mathrm{Tr}\,XP]\rangle = 0$: the kinetic term $K$ contributes $-2K$ (two factors of $P$, each lowered by commutation with $XP$), the potential term $V$ contributes $+4V$ (quartic in $X$), and the fermionic term $F$ contributes $+F$ (linear in $X$ with a single commutator).

(K.6) Virial theorem — equation 2 (energy conservation):
$$\langle K \rangle + \langle V \rangle + \langle F \rangle = E$$
Context: TeX label `virial_idea`, §2.2. Together with (K.5), these two equations determine $\langle K \rangle$ and $\langle F \rangle$ in terms of $\langle V \rangle$ and $E$. Eliminating $\langle F \rangle$ gives $2\langle K \rangle = \tfrac{2}{3}E + 2\langle V \rangle$ (TeX label `kinetic_pot`).

(K.7) Kinetic energy in terms of potential energy and total energy:
$$2\langle K \rangle = \frac{2}{3} E + 2\langle V \rangle$$
Context: TeX label `kinetic_pot`, §2.2. Derived by eliminating $\langle F \rangle$ between (K.5) and (K.6). Used to express $2\langle K\rangle = \tfrac{2}{3}E + 2\langle V\rangle$ (equivalently, $\langle K\rangle = \tfrac{1}{3}E + \langle V\rangle$) in the positivity constraint.

(K.8) Commutator bound from SO(9) positivity:
$$-\langle \mathrm{Tr}\, [X, Y]^2 \rangle = 2\langle \mathrm{Tr}\, X^2 Y^2 \rangle - 2\langle \mathrm{Tr}\, XYXY \rangle \le 4\langle \mathrm{Tr}\, X^4 \rangle$$
Context: TeX label `ineq_comm`, §2.2. Follows from positivity of two $2\times 2$ matrices of correlators built from $\{X^2, Y^2, XY, YX\}$. For an SO(9)-invariant state, summing over all pairs $(m,n)$ gives $4\langle V \rangle \le \tfrac{1}{g^2} \times 4 \times (9 \times 8)\langle \mathrm{Tr}\, X^4 \rangle$, i.e., $\langle V \rangle \le \tfrac{72}{g^2} \langle \mathrm{Tr}\, X^4 \rangle$. [Note: source line 303 writes $4\langle V\rangle = -\sum_{m,n}\langle\mathrm{Tr}[X^m,X^n]^2\rangle$ loosely without the explicit $g^{-2}$ factor; the correct accounting using $V = -\tfrac{1}{4g^2}\mathrm{Tr}[X_I,X_J]^2$ from the Hamiltonian (source line 188) gives the factor $g^{-2}$, consistent with the $144/g^2$ coefficient at source line 304.]

(K.9) Polchinski / bosonic lower bound on $\langle \mathrm{tr}\, \tilde{X}^4 \rangle$ (function of energy):
$$\langle \mathrm{tr}\, \tilde{X}^4 \rangle^{1/2} \left( 144\, \langle \mathrm{tr}\, \tilde{X}^4 \rangle + \frac{2}{3} \mathcal{E} \right) \ge \frac{9}{4}$$
where $\mathcal{E} = \lambda^{-1/3} E / N^2$ and $\tilde{X} = \lambda^{-1/3} X$.
Context: TeX label `Polchinski`, §2.2. Obtained by combining (K.4), (K.7), (K.8), plus the positivity matrix $\mathcal{M}_1 = \begin{pmatrix} \langle \mathrm{Tr}\, \mathbf{1} \rangle & \langle \mathrm{Tr}\, X^2 \rangle \\ \langle \mathrm{Tr}\, X^2 \rangle & \langle \mathrm{Tr}\, X^4 \rangle \end{pmatrix} \succeq 0$ (TeX label `Cm1`). At $\mathcal{E} = 0$: $144 \langle \mathrm{tr}\, \tilde{X}^4 \rangle^{3/2} \ge 9/4$, giving $\langle \mathrm{tr}\, \tilde{X}^4 \rangle \ge (9/(4\times 144))^{2/3} = 1/16$. The "little trace" convention $\mathrm{tr}\, \mathbf{1} = 1$ vs. $\mathrm{Tr}\, \mathbf{1} = N$ is used here (see Conventions).

(K.10) Fermionic operator definition:
$$F = \frac{1}{2} \gamma^I_{\alpha\beta} \, \mathrm{Tr}\left( \{\psi^\alpha, \psi^\beta\} X^I \right) \equiv \mathrm{Tr}\, O_I X^I$$
Context: §2.3 (no TeX label in source; inline equation in running text). Defines the auxiliary operator $O_I = \frac{1}{2} \gamma^I_{\alpha\beta} \{\psi^\alpha, \psi^\beta\}$. This is a bilinear in fermions. The key property is that $\langle \mathrm{Tr}\, O^I P_I \rangle = 0$ (from $\langle [H, F] \rangle = 0$), which zeros out an off-diagonal entry of $\mathcal{M}_2$.

(K.11) Fermionic contribution in terms of $V$ and $E$:
$$\langle F \rangle = 2\!\left(\frac{1}{3} E - \langle V \rangle\right)$$
Context: TeX label `fev`, §2.3. Derived by eliminating $\langle K \rangle$ between (K.5) and (K.6). The sign and coefficient are crucial: if $\langle V \rangle > E/3$ then $\langle F \rangle < 0$, and the fermionic term acts to lower the energy.

(K.12) The central positivity matrix $\mathcal{M}_2$:
$$\mathcal{M}_2 = \begin{pmatrix} \tfrac{1}{9}\langle \mathrm{Tr}\, O_I O_I \rangle & \tfrac{2}{9}\!\left(\tfrac{1}{3}E - \langle V \rangle\right) & 0 \\ \tfrac{2}{9}\!\left(\tfrac{1}{3}E - \langle V \rangle\right) & \langle \mathrm{Tr}\, X^2 \rangle & \tfrac{i}{2} N^2 \\ 0 & -\tfrac{i}{2} N^2 & \tfrac{2}{9}\!\left(\tfrac{1}{3}E + \langle V \rangle\right) \end{pmatrix} \succeq 0$$
Context: TeX label `Cm2`, §2.3. The rows/columns correspond (schematically) to operators $O_I$, $X_I$, and $P_I$. The $(2,3)$ entry $iN^2/2$ comes from the canonical commutation relations via $\langle \mathrm{Tr}\, XP \rangle = iN^2/2$. The upper-left entry is bounded by (K.13). The $(1,3)$ and $(3,1)$ zeros come from $\langle \mathrm{Tr}\, O^I P_I \rangle = 0$.

(K.13) Fermionic operator bound (from Majorana structure):
$$\frac{1}{9}\langle \mathrm{Tr}\, O_I O_I \rangle = \langle \mathrm{Tr}\, O_2 O_2 \rangle = \sum_{\alpha,\beta} s_\alpha s_\beta \langle \mathrm{Tr}\, \psi_\alpha^2 \psi_\beta^2 \rangle \le 64 N^3$$
Context: TeX label `fermionBd`, §2.3. The equality of the first two expressions holds because $\gamma^2$ is diagonal with eigenvalues $s_\alpha = \pm 1$ (8 positive, 8 negative). The bound $64 N^3$ is derived by solving a small SDP over fermionic correlators (Appendix, TeX label `result4`). This is tighter than the naive $O(N^4)$ estimate because fermionic anticommutator identities kill many terms.

(K.14) Lower bound on $\langle \mathrm{tr}\, \tilde{X}^2 \rangle$ (first line of the pair):
$$\langle \mathrm{tr}\, \tilde{X}^2 \rangle \ge \frac{(\mathcal{E} - 3v)^2}{9^3 \times 16} + \frac{27}{8(\mathcal{E} + 3v)}$$
Context: TeX label `firstLine`, §2.3. Here $v$ is the dimensionless potential energy treated as a free parameter over which we minimize. The source (line 366) says "$v$ is the boundary value of $\langle V\rangle$"; dimensional analysis of $v = 72\langle\mathrm{tr}\,\tilde{X}^4\rangle$ (line 374) and consistency with $\mathcal{E} = \lambda^{-1/3} E/N^2$ gives $v = \lambda^{-1/3}\langle V\rangle/N^2$ [not stated explicitly in source; inferred from dimensional analysis and $v = 72\langle\mathrm{tr}\,\tilde{X}^4\rangle$]. The right-hand side is derived from $\det\mathcal{M}_2 = 0$ with the fermionic bound (K.13) saturated.

(K.15) Constraint on $v$ at the boundary (second line of the pair):
$$\mathcal{E}^2 + \frac{3^9}{\mathcal{E} + 3v} = 9v^2$$
Context: TeX label `secondLine`, §2.3. This constraint fixes the optimal $v$ that minimizes the right-hand side of (K.14). At $E = 0$: the bound gives $\langle \mathrm{tr}\, \tilde{X}^2 \rangle \ge 3/16 \approx 0.1875$.

(K.16) Two-sided bound on $\gamma$ (the commutator non-commutativity ratio):
$$\gamma = \frac{-\langle \mathrm{tr}\, [X, Y]^2 \rangle}{\langle \mathrm{tr}\, X^2 \rangle \langle \mathrm{tr}\, Y^2 \rangle}, \qquad 0 \le \gamma \le \frac{v_\gamma}{18} \left[ \frac{4(\mathcal{E} - 3v_\gamma)^2}{9^3 \times 16} + \frac{27}{8(\mathcal{E} + 3v_\gamma)} \right]^{-2}$$
where $v_\gamma$ satisfies $(\mathcal{E} - 3v_\gamma)(\mathcal{E} + 3v_\gamma)^2 = 2 \times 3^9$.
Context: TeX label `gammaBd`, §2.3. The lower bound $\gamma \ge 0$ is trivial (follows from $-[X,Y]^2 \ge 0$ as a Hermitian operator). The upper bound is derived by reusing (K.14). This is the only quantity in the paper for which a two-sided bootstrap bound is achieved.

(K.17) Improved lower bound on $\langle \mathrm{tr}\, \tilde{X}^4 \rangle$ using fermionic constraints:
$$\langle \mathrm{tr}\, \tilde{X}^4 \rangle \ge (t_2)^2, \qquad v = 72(t_2)^2$$
$$\left(\frac{\mathcal{E}}{9} + \frac{v}{3}\right) \left(12\sqrt{2v} - \left(\frac{\mathcal{E}}{9} - \frac{v}{3}\right)^2\right) = 54$$
Context: TeX label `bigEconstr`, §2.3. Here $t_2$ is the optimization parameter defined by $(t_2)^2 = \langle\mathrm{tr}\,\tilde{X}^4\rangle$ at the boundary (i.e., $t_2 = \sqrt{\langle\mathrm{tr}\,\tilde{X}^4\rangle}$), and $v = 72(t_2)^2$. The improvement over (K.9) comes from using $\det\mathcal{M}_2 = 0$ with $v = 72\langle\mathrm{tr}\,\tilde{X}^4\rangle$ (from (K.8) saturated at its boundary). At $\mathcal{E} = 0$ this gives $\langle\mathrm{tr}\,\tilde{X}^4\rangle \ge ((7-4\sqrt{3})/256)^{1/3} \approx 0.06546 > 1/16$.

### Appendix C equations: fermionic matrix identities

(K.18) SU(N) generator definition and Casimir identities (Appendix C):
$$\mathrm{Tr}(T^A T^B) = \delta^{AB}, \qquad T^A T^A = \frac{N^2-1}{N}, \qquad \mathrm{Tr}\, T^A T^B T^A T^C = -\frac{1}{N}\delta^{BC}$$
Context: TeX labels `majorana` and `ttCas`, Appendix C. The first identity is the non-standard normalization (see Conventions). The second is the quadratic Casimir; the third is a quartic generator identity used to compute $\mathrm{Tr}\,\Psi^4$ and the off-diagonal fermionic bounds. Both identities in `ttCas` are required for the derivation of $\mathrm{Tr}\,\Psi^4$.

(K.19) Fermionic matrix trace identity:
$$\mathrm{Tr}\,\Psi^2 = \Psi^A \Psi^B \, \mathrm{Tr}(T^A T^B) = \Psi^A \Psi^A = \frac{1}{2}(N^2-1)$$
Context: TeX label `psi2`, Appendix C. Here $\Psi$ is any single fermionic matrix $\psi_\alpha$ (fixed $\alpha$, no sum). The second equality uses $\mathrm{Tr}(T^A T^B) = \delta^{AB}$ (K.18). The third equality uses the Majorana anticommutator identity: $(\psi_\alpha^A)^2 = \frac{1}{2}$ for each component (from $\{\psi_\alpha^A,\psi_\alpha^A\}=1$), so $\Psi^A\Psi^A = \sum_A (\psi_\alpha^A)^2 = \frac{1}{2}(N^2-1)$. This identity fixes the first row and column of the matrix $\mathcal{N}$ in (K.22).

(K.20) Quartic fermionic trace bound:
$$\mathrm{Tr}\,\Psi^4 = \frac{1}{2N}\!\left(N^4 - \frac{3N^2}{2} + \frac{1}{2}\right) < \frac{1}{2}N^3$$
Context: TeX label `psi4`, Appendix C. This is derived by repeated use of the Majorana anticommutator to reduce $\Psi^A\Psi^B\Psi^C\Psi^D$ products, using both identities in (K.18). The final inequality holds for all $N \ge 1$. This identity fixes the diagonal entries of $\mathcal{M}_{\alpha\alpha}$ in (K.22) via $\mathcal{M}_{\alpha\alpha} = N^{-3}\mathrm{Tr}\,\psi_\alpha^4 < 1/2$.

(K.21) Off-diagonal fermionic correlator bound:
$$\Psi^A \Psi^B \Phi^C \Phi^D \, \mathrm{Tr}\, T^A T^B T^C T^D = -\mathrm{Tr}(\Psi\Phi)(\Psi\Phi)^\dagger + \frac{(N^2-1)^2}{2N^2} < \frac{1}{2}$$
Context: TeX label `posAB`, Appendix C. Here $\Psi,\Phi$ are two different fermionic matrices ($\Psi = \psi_\alpha$, $\Phi = \psi_\beta$ with $\alpha\ne\beta$). The first step uses the anticommutator to anti-symmetrize; the second uses the quartic generator identity (K.18). The bound $< 1/2$ (strict) follows because $-\mathrm{Tr}(\Psi\Phi)(\Psi\Phi)^\dagger \le 0$. This gives $\mathcal{M}_{\alpha\beta} < 1/2$ for $\alpha\ne\beta$ in (K.22).

(K.22) Fermionic positivity matrix $\mathcal{N}$ (the $(1+16)\times(1+16)$ SDP):
$$\mathcal{N} = \begin{pmatrix} 1 & N^{-2}\,\mathrm{Tr}(\psi_\alpha)^2 \\ N^{-2}\,\mathrm{Tr}(\psi_\alpha)^2 & \mathcal{M}_{\alpha\beta} \end{pmatrix} \succeq 0, \qquad \mathcal{M}_{\alpha\beta} = \frac{1}{N^3}\langle \mathrm{Tr}\,\psi_\alpha^2 \psi_\beta^2 \rangle$$
Context: TeX label `MAB`, Appendix C. The matrix $\mathcal{N}$ is $(1+16)\times(1+16)$, with $\alpha,\beta = 1,\ldots,16$ labeling the 16 fermionic matrices. The first row/column is fixed by (K.19): $N^{-2}\mathrm{Tr}(\psi_\alpha)^2 = (N^2-1)/(2N^2) \approx 1/2$ at large $N$. The diagonal of $\mathcal{M}$ is fixed by (K.20). The off-diagonals are bounded by (K.21). Positivity $\mathcal{N}\succeq 0$ is imposed as the bootstrap constraint. The SDP over $\mathcal{N}$ maximizes $\sum_{\alpha,\beta} s_\alpha s_\beta \mathcal{M}_{\alpha\beta}$ subject to all the above constraints, giving (K.13)'s bound `result4`.

### Appendix D equation: SO(9) invariance and stronger X⁴ bound

(K.23) Stronger lower bound on $\langle\mathrm{tr}\,X^4\rangle$ from SO(9) rotational invariance:
$$\langle\mathrm{tr}\,X^4\rangle \ge \max\!\left\{-\tfrac{1}{4}\langle\mathrm{tr}\,[X,Y]^2\rangle,\;\; \tfrac{4}{11}\langle\mathrm{tr}\,[X,Y]^2\rangle + \tfrac{27}{11}\langle\mathrm{tr}\,X^2\rangle^2 \right\}$$
Context: TeX label `strongerSO9`, Appendix D (source line 776). All three quantities $\langle\mathrm{tr}\,X^4\rangle$, $\langle\mathrm{tr}\,[X,Y]^2\rangle$, $\langle\mathrm{tr}\,X^2\rangle^2$ use the same variable $X$ (plain, dimensionful) and little-trace $\mathrm{tr} = \mathrm{Tr}/N$ throughout; mixing with $\tilde{X} = \lambda^{-1/3}X$ is valid only if all three terms are simultaneously rescaled. To express the bound in dimensionless units, replace every $X \to \tilde{X}$: the equation is homogeneous of degree 4 so it transforms covariantly. Derived by constructing the full positivity matrix $\mathcal{M}_4$ over operators $\{1, X^I, X^I X^J\}$ and imposing SO(9) rotational invariance. The SO(9) singlet structure reduces all quartic correlators to two parameters $A_4, B_4$ via $\langle\mathrm{Tr}(X^I X^J X^K X^L)\rangle = A_4(\delta^{IJ}\delta^{KL}+\delta^{JK}\delta^{IL}) + B_4\delta^{IK}\delta^{JL}$, with $\mathrm{Tr}\,X^4 = 2A_4+B_4$ and $\mathrm{Tr}[X,Y]^2 = 2(B_4-A_4)$ (source line 772; note big-$\mathrm{Tr}$ here). The constant $27/11$ is $D=9$-dependent. The weaker bound $\langle\mathrm{tr}\,X^4\rangle \ge \langle\mathrm{tr}\,X^2\rangle^2$ is a corollary. The paper notes (line 779) that incorporating (K.23) into the main bootstrap analysis did not improve the bounds of Figure 1.

## Conventions

**Note: No `GPD/CONVENTIONS.md` exists yet. The following documents the conventions used in this paper; they should be established in `CONVENTIONS.md` when it is created.**

- **Trace conventions (critical):** The paper uses TWO distinct trace operations. "Big Trace" $\mathrm{Tr}$ satisfies $\mathrm{Tr}\, \mathbf{1} = N$ (i.e., traces over the $N \times N$ matrices). "Little trace" $\mathrm{tr}$ satisfies $\mathrm{tr}\, \mathbf{1} = 1$, so $\mathrm{tr} = \mathrm{Tr}/N$. Bounds on dimensionless quantities are expressed using $\mathrm{tr}$; raw commutator identities use $\mathrm{Tr}$. **Mixing these up is the single most likely source of numerical error when implementing the bootstrap.**

- **SU(N) generators:** $\{T_A\}$ with $\mathrm{Tr}(T^A T^B) = \delta^{AB}$, so the generators are orthonormal (not the usual $\mathrm{Tr}(T^A T^B) = \frac{1}{2}\delta^{AB}$). This affects factors in $T^A T^A = (N^2-1)/N$ and $\mathrm{Tr}\, T^A T^B T^A T^C = -(1/N)\delta^{BC}$. Flag: this normalization differs from the most common physics convention of $\mathrm{Tr}(T^A T^B) = \frac{1}{2}\delta^{AB}$; many standard results need factors of $\sqrt{2}$.

- **Coupling constant:** $g^2$ has units of $E^3$ (energy cubed, in natural units with $\hbar = 1$). The 't Hooft coupling is $\lambda = g^2 N$, which is also dimensionful. The dimensionless expansion parameter at temperature $T$ is $\lambda/T^3$. The combination $\lambda^{1/3}$ sets the energy scale.

- **Dimensionless rescalings used throughout:** $\tilde{X} = \lambda^{-1/3} X$, $\mathcal{E} = \lambda^{-1/3} E/N^2$. The variable $v$ appearing in (K.14)–(K.15) and (K.17) satisfies $v = \lambda^{-1/3}\langle V\rangle/N^2$ [not stated explicitly in source; inferred from dimensional analysis: $v$ must be dimensionless and match the scaling of $\mathcal{E}$; this is consistent with the source's explicit relation $v = 72\langle\mathrm{tr}\,\tilde{X}^4\rangle$]. All bootstrap bounds on physical quantities are stated in these units; translating back to physical units requires restoring factors of $\lambda^{1/3}$ and $N^2$.

- **SO(9) gamma matrices:** The 9 gamma matrices $\gamma^I$ satisfy $\{\gamma^I, \gamma^J\} = 2\delta^{IJ}$ and are taken to be real, traceless, and symmetric $16 \times 16$ matrices. The specific matrix $\gamma^2$ is diagonal with $s_\alpha = +1$ for $\alpha = 1,\ldots,8$ and $s_\alpha = -1$ for $\alpha = 9,\ldots,16$.

- **State convention:** The bounds apply to any density matrix $\rho$ with $\langle H \rangle = E$ and $[H, \rho]$ negligible in the large-$N$ limit. This is NOT the same as a pure energy eigenstate; it is a quasi-stationary state modeling the metastable black hole.

- **Large-N limit:** 't Hooft limit: $N \to \infty$ with $\lambda = g^2 N$ fixed, and $\lambda/T^3$ fixed. In this limit, large-N factorization allows restricting to single-trace operators. The bounds in the paper largely do NOT use large-N explicitly (the authors note this); they apply at any $N$.

- **Sign of potential $V$:** In the decomposition $H = K + V + F$, the potential is $V = -\frac{1}{4g^2}\mathrm{Tr}\,[X_I,X_J]^2$. Since $X_I, X_J$ are Hermitian, $[X_I,X_J]$ is anti-Hermitian and can be written as $iM$ for some Hermitian $M$. Therefore $-[X_I,X_J]^2 = -(iM)^2 = M^2 \ge 0$ (positive semi-definite), so $V \ge 0$. The bound (K.8) uses $-\langle\mathrm{Tr}\,[X,Y]^2\rangle \ge 0$.

## Derivation Sketches

### Sketch 1: Deriving $\mathcal{M}_2 \succeq 0$ and the bound on $\langle \mathrm{tr}\, \tilde{X}^2 \rangle$

Step 1. Apply $\langle [H, \mathrm{Tr}\, X^2] \rangle = 0$. This gives $\langle \mathrm{Tr}\, XP + PX \rangle = 0$, so by the canonical commutation relations $\langle \mathrm{Tr}\, XP \rangle = iN^2/2$ and $\langle \mathrm{Tr}\, PX \rangle = -iN^2/2$.

Step 2. Apply $\langle [H, \mathrm{Tr}\, XP] \rangle = 0$. This yields $-2\langle K \rangle + 4\langle V \rangle + \langle F \rangle = 0$ (virial). Combined with $\langle H \rangle = E$ this gives (K.7) and (K.11).

Step 3. Rewrite $F = \mathrm{Tr}\, O_I X^I$ (K.10). Apply $\langle [H, F] \rangle = 0$, using the canonical commutation relations. The result is $\langle \mathrm{Tr}\, O^I P_I \rangle = 0$, zeroing out the $(1,3)$ entry of $\mathcal{M}_2$.

Step 4. Assemble the three operators $\{O_I, X_I, P_I\}$ and compute the $3 \times 3$ inner product matrix. Positivity of the inner product on the Hilbert space forces $\mathcal{M}_2 \succeq 0$.

Step 5. Bound the $(1,1)$ entry using the fermionic SDP (K.13). The Majorana structure means $\psi_\alpha^2$ is at most $\mathcal{O}(N^2)$ per site, so $\mathrm{Tr}\, \psi_\alpha^2 \psi_\beta^2 = \mathcal{O}(N^3)$ rather than $\mathcal{O}(N^4)$.

Step 6. Minimize $\langle \mathrm{tr}\, \tilde{X}^2 \rangle$ over the dimensionless free parameter $v = \lambda^{-1/3}\langle V\rangle/N^2$ subject to $\mathcal{M}_2 \succeq 0$ and the commutator bound (K.8). Setting $\det \mathcal{M}_2 = 0$ at the boundary gives (K.14)–(K.15).

### Sketch 2: The bosonic / Polchinski bound

The argument is a two-round bootstrap. Round 1 gives the uncertainty relation (K.4). Round 2 replaces $\langle K \rangle$ using the virial theorem (K.7), and bounds $\langle K \rangle$ from below in terms of $\langle \mathrm{Tr}\, X^4 \rangle$ via the commutator bound (K.8). The combined positivity constraint (K.9) then bounds $\langle \mathrm{tr}\, \tilde{X}^4 \rangle$.

### Sketch 3: Fermionic operator bound (K.13)

The bound is derived in Appendix C of the paper (TeX label `fermionMatrices`). The derivation chain is:

1. Set up the SU(N) generator identities (K.18): $\mathrm{Tr}(T^A T^B) = \delta^{AB}$, $T^A T^A = (N^2-1)/N$, $\mathrm{Tr}\,T^A T^B T^A T^C = -(1/N)\delta^{BC}$.
2. Infer the first row and column of $\mathcal{N}$ using (K.19): $\mathrm{Tr}\,\Psi^2 = \frac{1}{2}(N^2-1)$; infer the diagonal of $\mathcal{M}$ using (K.20): $\mathrm{Tr}\,\Psi^4 = \frac{1}{2N}(N^4 - 3N^2/2 + 1/2) < \frac{1}{2}N^3$. (Source line 726: "Using \nref{psi2}, we may infer the value of the first row and column of $\mathcal{N}$, and using \nref{psi4}, we learn the values of the diagonal.")
3. Bound the off-diagonals using (K.21): $\mathcal{M}_{\alpha\beta} = N^{-3}\langle\mathrm{Tr}\,\psi_\alpha^2\psi_\beta^2\rangle < 1/2$ for $\alpha\ne\beta$.
4. Assemble the $(1+16)\times(1+16)$ positivity matrix $\mathcal{N}$ (K.22) with known diagonal entries and bounded off-diagonals.
5. Solve the SDP: maximize $\sum_{\alpha\beta} s_\alpha s_\beta \mathcal{M}_{\alpha\beta}$ subject to $\mathcal{N}\succeq 0$. The result is $\le 64(1-\epsilon')$ where $\epsilon'\to 0$ at large $N$ (TeX label `result4`). This gives the bound $\le 64 N^3$ in (K.13).

## Connections

- **Polchinski 1999 (arXiv:hep-th/9903165):** The bound (K.9) at $E = 0$ reproduces Polchinski's virial argument, which is both extended to finite energy and corrected (Polchinski had a factor-of-4 error in his equation 7.4, noted in footnote 4 of the paper).

- **Han-Hartnoll-Kruthoff 2020 (arXiv:2004.10212):** The bootstrap framework used here is the quantum mechanical bootstrap of Han et al. The paper cites this as the primary methodological reference.

- **Pateloudis et al. 2022 (arXiv:2210.04881):** The Monte Carlo data for $\langle \mathrm{tr}\, \tilde{X}^2 \rangle$ vs. temperature comes from this reference; Figure 2 of the paper compares the bootstrap lower bound against these results.

- **Itzhaki-Maldacena-Sonnenschein-Yankielowicz 1998 (arXiv:hep-th/9802042):** The holographic dictionary and the thermodynamics formula (K.3) come from this reference.

- **BMN model (Berenstein-Maldacena-Nastase, arXiv:hep-th/0202021):** The regulator used in Monte Carlo (adding mass deformation $\mu$ to prevent flat directions) is the BMN model. The bootstrap bounds of this paper are stated for pure BFSS (no mass deformation), so systematic errors in the Monte Carlo from finite $\mu$ are expected to be small.

- **Future work:** The paper explicitly calls for (a) numerical SDP implementation using SDPB or similar, (b) organizing operators into SO(9) multiplets, (c) bootstrapping time-dependent (off-diagonal) correlators, and (d) using large-N factorization more explicitly to work directly in the 't Hooft limit.

## Open Questions

1. **Holographic interpretation of $\langle \mathrm{Tr}\, X^\ell \rangle$:** The paper notes (Appendix A) that the holographic dual of simple matrix one-point functions is not well understood. A quantitative bulk calculation would give a target for the bootstrap.

2. **Upper bound on $\langle \mathrm{tr}\, \tilde{X}^2 \rangle$:** The paper obtains only a lower bound. There is no upper bound derived; the question of what imposes an upper bound (if any) is open.

3. **Numerical bootstrap:** The paper performs only the analytic first-few-rounds bootstrap. A systematic numerical SDP (e.g., using SDPB) incorporating many more operators and SO(9) representation theory has not been done.

4. **Large-N factorization in the bootstrap:** The bounds in this paper do not use large-N factorization. Incorporating it explicitly should both tighten the bounds and resolve the subtlety of divergent correlators at finite $N$.

5. **Fermionic (SUSY) constraints:** The paper uses the fermionic structure of the Hamiltonian but not supersymmetry directly. Constraints from the supercharge $Q |E=0\rangle = 0$ and localization could in principle be fed into the bootstrap.

6. **BMN deformation extrapolation:** Whether the bound applies exactly to the Monte Carlo results (which use a small but nonzero $\mu$) requires understanding the $\mu \to 0$ limit more carefully.

7. **The $\ell \ge 9$ divergence:** Susskind's argument (cited by Polchinski) that $\langle \mathrm{Tr}\, X^\ell \rangle$ diverges for $\ell \ge 9$ in the ground state. If this is correct it constrains what the bootstrap can bound.

## Traps and Subtleties

**These are the most important warnings for a downstream user of this document.**

1. **The two trace conventions must never be mixed.** The paper uses $\mathrm{Tr}$ ($\mathrm{Tr}\,\mathbf{1} = N$) for algebraic derivations and $\mathrm{tr}$ ($\mathrm{tr}\,\mathbf{1} = 1$) for the final dimensionless bounds. The bounds in equations (K.9), (K.14)–(K.15) are expressed in $\mathrm{tr}$. If you write code that evaluates these bounds using $\mathrm{Tr}$ quantities without dividing by $N$, all numerical answers will be wrong by factors of $N$.

2. **The state $\rho$ is NOT a thermal density matrix.** The bounds hold for any state with $\langle H \rangle = E$ and $[H, \rho] \approx 0$. At finite $N$, all excited states are scattering states and $\langle \mathrm{Tr}\, X^\ell \rangle$ diverges. The paper sidesteps this by working in the large-$N$ limit where metastable black hole states have $[H, \rho]$ suppressed by $1/N$. Any comparison with canonical-ensemble (thermal) Monte Carlo data implicitly assumes that the microcanonical and canonical ensembles agree at large $N$.

3. **The fermionic bound (K.13) is saturated at the optimum.** Setting $\langle \mathrm{Tr}\, O_2 O_2 \rangle = 64 N^3$ is not a derived fact but an optimization choice: the bound on $\langle \mathrm{Tr}\, X^2 \rangle$ is minimized when this entry is at its maximum. In a physical state, $\langle \mathrm{Tr}\, O_2 O_2 \rangle$ need not equal $64N^3$; the bound only says it cannot exceed this value.

4. **The factor of 4 error in Polchinski (1999).** The paper corrects a factor-of-4 error in equation 7.4 of Polchinski (1999). The correct uncertainty bound is $\langle \mathrm{Tr}\, X^2 \rangle \langle \mathrm{Tr}\, P^2 \rangle \ge \frac{9}{4} N^4$, not $\frac{9}{16} N^4$. Any comparison with Polchinski's original numbers must account for this.

5. **The SU(N) generator normalization differs from the standard.** The paper uses $\mathrm{Tr}(T^A T^B) = \delta^{AB}$. In the standard physics convention one uses $\mathrm{Tr}(T^A T^B) = \frac{1}{2}\delta^{AB}$. The Casimir identities $T^A T^A = (N^2-1)/N$ and $\mathrm{Tr}\, T^A T^B T^A T^C = -(1/N)\delta^{BC}$ are derived in this normalization and will give different numerical values if you switch normalizations without adjusting.

6. **The commutator bound (K.8) requires SO(9) invariance of the state.** The relation $4\langle V \rangle \le 4 \times (9 \times 8) \langle \mathrm{Tr}\, X^4 \rangle$ uses the fact that all 9 matrices have the same expectation values ($SO(9)$ rotational invariance). Breaking this symmetry (e.g., by restricting to a subsector or considering anisotropic initial conditions) invalidates the numerical coefficient.

7. **The gravity thermodynamics formula (K.3) is valid only for $T^3 \ll \lambda$.** The transition in the bootstrap bound at $\mathcal{E} \sim 1$ (i.e., $E/N^2 \sim \lambda^{1/3}$) corresponds to the breakdown of the supergravity approximation. Above this energy, $\alpha'$ corrections modify the thermodynamics, and the bound's transition loses its holographic interpretation. Do not use (K.3) to compare bootstrap results at $T \gtrsim \lambda^{1/3}$.

8. **Large-N factorization is used implicitly but not enforced.** The bootstrap matrix $\mathcal{M}_2$ treats $\langle \mathrm{Tr}\, O_I O_I \rangle$ and $\langle \mathrm{Tr}\, X^2 \rangle$ as independent variables, ignoring large-N factorization (which would require $\langle \mathrm{Tr}\, O_I O_I \rangle \approx \langle \mathrm{Tr}\, O_I \rangle \langle \mathrm{Tr}\, O_I \rangle$). At large $N$, imposing factorization should tighten the bounds. The current bounds are therefore likely conservative.

9. **$\langle V \rangle$ and $v$ are not independent of $\langle \mathrm{Tr}\, X^4 \rangle$.** The relationship $\langle V \rangle \le \tfrac{72}{g^2} \langle \mathrm{Tr}\, X^4 \rangle$ (from (K.8); note the $g^{-2}$ factor) means that when you use $v = \lambda^{-1/3}\langle V\rangle/N^2$ as a free optimization variable in (K.14)–(K.15), the range of $v$ is constrained by other variables. If you try to implement this numerically, make sure the constraint (K.8) is enforced as a separate inequality, not forgotten.

10. **The bounds on $\langle \mathrm{tr}\, \tilde{X}^4 \rangle$ in Figure 1 of the paper come from multiple constraints.** The best bound (solid black curve) uses all of (K.8), $\mathcal{M}_1 \succeq 0$, and $\det \mathcal{M}_2 = 0$. The red dashed curve uses only (K.4) + (K.7) + (K.8) + $\mathcal{M}_1 \succeq 0$. These are not the same and should not be conflated.

11. **The fermionic SDP bound $\le 64$ is only exact at large $N$.** The precise result (TeX label `result4`) is $\sum_{\alpha\beta} s_\alpha s_\beta \mathcal{M}_{\alpha\beta} \le 64(1-\epsilon')$, where $\epsilon' > 0$ is a positive correction that vanishes as $N\to\infty$. The source drops $\epsilon'$ for the large-$N$ analysis. Any finite-$N$ implementation of the bootstrap should restore $\epsilon'$ to obtain slightly stronger bounds; the paper notes this would "strengthen the bounds at finite $N$ by a very slight amount."

12. **The $\mathrm{tr}\,\Psi^2$ identity (K.19) holds for a single fixed fermionic matrix $\psi_\alpha$, not a sum.** The value $\frac{1}{2}(N^2-1)$ is for one $\alpha$; summing over all 16 spinor components gives $8(N^2-1)$. Do not confuse $\mathrm{Tr}\,\psi_\alpha^2$ (single $\alpha$) with $\sum_\alpha\mathrm{Tr}\,\psi_\alpha^2$.
