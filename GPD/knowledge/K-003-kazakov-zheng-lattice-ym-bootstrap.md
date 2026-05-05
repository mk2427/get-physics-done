---
kdoc_id: K-003-kazakov-zheng-lattice-ym-bootstrap
status: Stable
topic: "Bootstrap for lattice Yang-Mills theory at large N_c (Kazakov-Zheng)"
cluster: bfss-bootstrap
sources:
  - "arXiv:2203.11360 [hep-th] — V. Kazakov and Z. Zheng, 'Bootstrap for Lattice Yang-Mills theory'"
created: 2026-04-27
last_reviewed: 2026-04-27
review_rounds: 3
superseded_by: null
eqn_ref_schema_version: 1
assertion_schema_version: 1
layout: single
---

# Knowledge: Bootstrap for Lattice Yang-Mills Theory (Kazakov-Zheng 2022)

## Overview

This document covers the bootstrap study of $SU(\infty)$ lattice Yang-Mills theory (LYM) in dimensions $D = 2, 3, 4$, carried out by Kazakov and Zheng in arXiv:2203.11360. The paper is a major development in using Makeenko-Migdal loop equations (LEs) combined with positivity constraints and symmetry reduction to obtain rigorous upper and lower bounds on Wilson loop averages — specifically the plaquette average $u_P = \frac{1}{N_c} \langle \mathrm{tr}\, U_P \rangle$ — without Monte Carlo simulation. It is directly inspired by the same authors' earlier matrix bootstrap paper (arXiv:2104.13672) and the pioneering Anderson-Kruczenski work (arXiv:1612.08760, arXiv:1811.06171).

The core algorithm has four ingredients. First, positivity of correlation matrices of Wilson loop averages (WAs) — arising from Hermitian conjugation (path reversal) on the lattice. Second, reflection positivity matrices from the three types of lattice reflection symmetry (site, link, diagonal), which provide additional semidefinite constraints and substantially tighten the bounds. Third, a convex relaxation that linearizes the nonlinear LEs by promoting the product $W_i W_j$ to an independent matrix variable $Q_{ij}$ subject to a semidefinite constraint. Fourth, symmetry reduction (Invariant SDP) using the lattice symmetry group $B_d \times \mathbb{Z}_2$, which block-diagonalizes the large positivity matrices and makes the semidefinite program (SDP) computationally tractable.

The main quantitative achievement is as follows. For $D = 4$ and loop cutoff $L_\mathrm{max} = 16$, the lower bounds track the Monte Carlo data in the strong-coupling phase and the upper bounds reproduce the 3-loop perturbation theory in the weak-coupling phase. The 4D first-order phase transition is located at $\lambda_c \approx 2.9$. The 2D exact solution (Gross-Witten-Wadia) is recovered as a benchmark. For $D = 3$, convergence with $L_\mathrm{max}$ is observed but is slower than in 4D. All computations were done on a single workstation; each 4D data point requires approximately 20 hours CPU time at $L_\mathrm{max} = 16$.

The scale of the SDP is noteworthy. At $L_\mathrm{max} = 16$ there are approximately 40,000 LEs in 3D and approximately 100,000 LEs in 4D, of which more than 80% are back-track loop equations. Without symmetry reduction the correlation matrix for $0 \to 0$ paths in 3D at $L_\mathrm{max} = 16$ is $6505 \times 6505$; after symmetry reduction it factorizes into 20 blocks of sizes listed in (K.9) below. The resulting SDP is solved using MOSEK.

For the BFSS bootstrap project, this paper is the closest methodological predecessor in the gauge/matrix bootstrap direction: it demonstrates that the loop-equation + positivity + relaxation + symmetry-reduction strategy works at scale for a lattice gauge theory and produces bounds competitive with Monte Carlo. The specific equations — Wilson action, loop equations, positivity constraints, convex relaxation — are the direct precursors of what one would set up for the BFSS matrix quantum mechanics in the loop-operator language.

## Physical Picture

The Makeenko-Migdal loop equations are the Schwinger-Dyson equations for Wilson loop averages in the large-$N_c$ limit. They arise from invariance of the path-integral measure under $U_l \to U_l(1 + i\epsilon)$ shifts of individual link variables. The key structural property is that, at $N_c = \infty$, the LEs close on single-trace WAs $W[C]$ because multi-trace correlators factorize: $\langle \frac{1}{N_c}\mathrm{tr}\, A \cdot \frac{1}{N_c}\mathrm{tr}\, B \rangle \to \langle \frac{1}{N_c}\mathrm{tr}\, A \rangle \langle \frac{1}{N_c}\mathrm{tr}\, B \rangle$. This factorization is what makes the right-hand side of the MMLE nonlinear (a product of two WAs). The back-track LEs arise by varying links on "back-track" paths appended to a Wilson loop vertex; although back-tracks are the identity when inserted into a loop, their SD variation yields independent linear and nonlinear constraints that constitute more than 80% of all LEs at practical cutoffs.

The bootstrap strategy exploits two independent sources of constraints. The positivity conditions say that any inner product $\langle \mathcal{O}^\dagger \mathcal{O} \rangle \geq 0$ forces the matrix $\mathcal{M}_{ij} = \langle \mathcal{O}_i^\dagger \mathcal{O}_j \rangle$ of WAs to be positive semidefinite. For Wilson loops, Hermitian conjugation is path reversal, so the correlation matrix entries are WAs of closed loops obtained by joining a forward and reversed open path. Reflection symmetries of the lattice supply three additional families of positive-semidefinite matrices (site-reflection, link-reflection, diagonal-reflection), each with a different invariant subgroup of $B_d \times \mathbb{Z}_2$. Combining these with the LEs (as linear or linearized equalities) and the convex relaxation of quadratic terms gives an SDP that is both rigorous and computationally tractable when the symmetry reduction is applied.

The convex relaxation deserves emphasis. The exact problem requires $Q_{ij} = W_i W_j$ (rank-1 constraint), which is non-convex. The relaxation replaces this with the semidefinite condition $\begin{pmatrix} 1 & W^T \\ W & Q \end{pmatrix} \succeq 0$, which is convex and whose feasible set contains the exact rank-1 manifold. Solutions of the SDP that satisfy this constraint but have $\mathrm{rank}(Q) > 1$ are "non-physical" in the sense that they do not correspond to genuine WA configurations; they are artifacts of the relaxation. Tightening the bounds by increasing $L_\mathrm{max}$ forces the feasible set of the relaxed SDP closer to the exact set.

## Key Results

1. **Wilson action (eq. `eq: action`)**: $S = -(N_c/\lambda) \sum_P \mathrm{Re}\, \mathrm{tr}\, U_P$, summing over all plaquettes $P$ in both orientations. This is the starting point. See (K.1).

2. **Wilson loop averages (eq. `WA`)**: $W[C] = \langle (\mathrm{tr}/N_c) \prod_{l \in C} U_l \rangle$ at $N_c \to \infty$. The LEs close on these objects due to large-$N_c$ factorization. See (K.2).

3. **Makeenko-Migdal loop equations (eq. `MMLE`)**: Schwinger-Dyson equations relating the "loop derivative" of $W[C]$ (inserting a plaquette around each link of $C$) to a sum over self-intersection products $W[C_{ll'}] W[C_{l'l}]$. They are linear in WAs on the left and quadratic (factorized) on the right. See (K.3).

4. **Positivity / semidefinite condition (eq. `qform`)**: $\langle \mathcal{O}^\dagger \mathcal{O} \rangle = \alpha^{*T} \mathcal{M} \alpha \geq 0 \Leftrightarrow \mathcal{M} \succeq 0$ for any coefficient vector $\alpha$. This is the master positivity condition from which all correlation and reflection matrices derive. See (K.4).

5. **Convex relaxation of nonlinear LEs**: Replace $Q_{ij} = W_i W_j$ with the semidefinite constraint $\begin{pmatrix} 1 & W^T \\ W & Q \end{pmatrix} \succeq 0$. The relaxation matrix has rank 1 exactly when $Q_{ij} = W_i W_j$. See (K.5).

6. **Symmetry reduction / Invariant SDP (projector formula)**: Block-diagonalize positivity matrices by projecting onto irreps of $G = B_d \times \mathbb{Z}_2$ (correlation matrices) or its subgroups (reflection matrices). Projector to irrep $k$: $P_k = \frac{\dim(\mathrm{Rep}_k)}{\dim G} \sum_{g \in G} r_{11}(g^{-1}) g$. See (K.6).

7. **3-loop perturbation theory in 4D (eq. `PLg`)**: $u_P = 1 - \lambda/8 - 0.005107\lambda^2 - 0.000794\lambda^3 + \mathcal{O}(\lambda^4)$ at $N_c = \infty$. Upper bootstrap bounds reproduce this to high accuracy in the weak-coupling phase. See (K.7).

8. **Strong-coupling expansion in 4D (eq. `SCexp`)**: $u_P = 1/\lambda + 4/\lambda^5 + 60/\lambda^9 + 136/\lambda^{11} + 1092/\lambda^{13} + \mathcal{O}(\lambda^{-15})$. Valid beyond the first-order phase transition $\lambda_c \approx 2.9$. Lower bootstrap bounds track this in the strong-coupling phase. See (K.8).

9. **2D exact solution (eq. `exact2D`)**: $u_P = 1 - \lambda/4$ for $\lambda \leq 2$; $u_P = 1/\lambda$ for $\lambda \geq 2$. Phase transition at $\lambda = 2$ (Gross-Witten-Wadia large-$N$ transition). See (K.10).

10. **Symmetry-reduced block sizes in 3D at $L_\mathrm{max} = 16$**: The $6505 \times 6505$ correlation matrix block-diagonalizes into 20 blocks of sizes 38, 15, 25, 18, 62, 33, 68, 75, 56, 78, 22, 18, 34, 15, 56, 33, 57, 76, 69, 73. See (K.9).

11. **Invariant groups for positivity matrices** (Table 1 of paper): Listed for $D = 2, 3, 4$; the correlation matrix has invariant group $B_d \times \mathbb{Z}_2$, while site/link and diagonal reflection matrices have the subgroups listed in (K.11).

12. **$L_\mathrm{max} = 8$ worked example in 2D** (Supplementary Material): With six independent WAs $\mathcal{W}_1, \ldots, \mathcal{W}_6$ (where $\mathcal{W}_1 = u_P$), the two loop equations (eq. `loop`) and the symmetry-reduced positivity conditions (eq. `sym`) form a complete SDP. At $\lambda = 2$: $0 \leq \mathcal{W}_1 \leq 0.69300$. See (K.12) and (K.13).

## Equations

All equations verified against the TeX source `2203.11360.tex`. None extracted from OCR; all taken directly from TeX source.

(K.1) Wilson action — TeX label `eq: action`, §2 (Yang-Mills Loop equations at Large N):
$$S = -\frac{N_c}{\lambda} \sum_{P} \mathrm{Re}\, \mathrm{tr}\, U_P$$
Context: $U_P$ is the ordered product of four $SU(N_c)$ unitary link matrices around plaquette $P$; the sum runs over all plaquettes in both orientations. $\lambda = g^2 N_c$ is the 't Hooft coupling (bare). $\mathrm{tr}$ is the full (unnormalized) trace.
Why/How: Wilson action in the standard plaquette form. The $-N_c/\lambda$ prefactor means that in the continuum limit $a_L \to 0$ one recovers the continuum Yang-Mills action $\frac{1}{4g^2} \int F^2$ up to $O(a_L^2)$ corrections. Large $\lambda$ is strong coupling; small $\lambda$ is weak coupling.

(K.2) Wilson loop averages (WA) — TeX label `WA`, §2:
$$W[C] = \left\langle \frac{\mathrm{tr}}{N_c} \prod_{l \in C} U_l \right\rangle$$
Context: $C$ is an oriented closed lattice loop; $l \in C$ are its constituent links traversed in order; the product is a matrix product of $SU(N_c)$ link matrices. $\mathrm{tr}/N_c$ is the normalized trace. At $N_c \to \infty$, $W[C]$ are classical (c-number) variables on loop space.
Why/How: WAs are the fundamental gauge-invariant observables. The large-$N_c$ factorization $\langle (\mathrm{tr}/N_c)\, A \cdot (\mathrm{tr}/N_c)\, B \rangle \to W[A] \cdot W[B]$ is what closes the LEs on single-trace WAs and renders the right-hand side of (K.3) a product of two WAs rather than a connected correlator.

(K.3) Makeenko-Migdal loop equations — TeX label `MMLE`, §2:
$$\sum_{\nu \perp \mu} \left( W[C_{l_\mu} \cdot \overrightarrow{\delta C^\nu_{l_\mu}}] - W[C_{l_\mu} \cdot \overleftarrow{\delta C^\nu_{l_\mu}}] \right) = \lambda \sum_{\substack{l' \in C \\ l' \sim l}} \epsilon_{ll'}\, W[C_{ll'}]\, W[C_{l'l}]$$
Context: Schwinger-Dyson equations for WAs; §2 and Fig. 2 of paper. Obtained from invariance of the path-integral measure under $U_l \to U_l(1 + i\epsilon)$. LHS: the "loop operator" acts on link $l_\mu$ by inserting the plaquette $\overrightarrow{\delta C^\nu_{l_\mu}}$ or $\overleftarrow{\delta C^\nu_{l_\mu}}$ in the $\mu\nu$-plane around that link, summing over all $2(D-1)$ transverse directions $\nu$. RHS: sum over all occurrences $l'$ of the same link $l$ in the loop $C$; $\epsilon_{ll'} = +1$ for opposite orientation, $\epsilon_{ll'} = -1$ for colinear orientation (TeX §2, p. 2: "ε_{ll'}=±1 for links l and l' with opposite or colinear orientation, respectively"); the contour $C$ splits as $C \to C_{ll'} \cdot C_{l'l}$.
Why/How: LEs are linear on the LHS and nonlinear (products of WAs) on the RHS due to factorization. The nonlinearity is the central difficulty; it is handled by convex relaxation (K.5). LEs close on single-trace WAs at $N_c = \infty$ only; at finite $N_c$, multi-trace operators appear on the RHS.

(K.4) Positivity / semidefinite condition — TeX label `qform`, §3.1:
$$\langle \mathcal{O} | \mathcal{O} \rangle = \langle \mathcal{O}^\dagger \mathcal{O} \rangle = \alpha^{*T} \mathcal{M}\, \alpha \geq 0 \quad \Leftrightarrow \quad \mathcal{M} \succeq 0$$
Context: Master positivity condition. $\mathcal{O} = \sum_i \alpha_i \mathcal{O}_i$ is an arbitrary linear combination of basis operators $\mathcal{O}_i$ (here: Wilson open paths or loops) with arbitrary complex coefficients $\alpha_i$. $\mathcal{M}_{ij} = \langle \mathcal{O}_i^\dagger \mathcal{O}_j \rangle$.
Why/How: Since $\alpha$ is arbitrary, $\langle \mathcal{O}^\dagger \mathcal{O} \rangle \geq 0$ for ALL $\alpha$ if and only if $\mathcal{M} \succeq 0$. For Wilson paths, $\mathcal{O}_i^\dagger$ corresponds to path reversal (Hermitian conjugation of the ordered product of link matrices). For reflection symmetries, $\mathcal{O}_i^\dagger$ corresponds to the reflected path. All entries $\mathcal{M}_{ij}$ are WAs of closed loops formed by joining path $i$ and the conjugate of path $j$.

(K.5) Convex relaxation — §3.2:
$$Q_{ij} = W_i W_j \quad \overset{\text{replace}}{\Longrightarrow} \quad \begin{pmatrix} 1 & W^T \\ W & Q \end{pmatrix} \succeq 0$$
Context: $W = \{W_1, W_2, W_3, \ldots\}$ is the column vector of all inequivalent WAs (the bootstrap variables); $Q$ is the matrix of all pairwise products, elevated to an independent matrix variable. The condition $\begin{pmatrix} 1 & W^T \\ W & Q \end{pmatrix} \succeq 0$ is by Schur complement equivalent to $Q - W W^T \succeq 0$, i.e., $Q \geq W W^T$ in the PSD sense.
Why/How: The exact constraint $Q_{ij} = W_i W_j$ is a rank-1 condition and non-convex. The SDP relaxation is convex and includes the exact solution in its feasible set. The relaxation matrix has rank 1 if and only if $Q_{ij} = W_i W_j$ exactly. By increasing $L_\mathrm{max}$, the LEs add more linear constraints that progressively cut away relaxed-but-non-physical solutions, tightening the bounds.

(K.6) Invariant SDP projector formula — §3.3:
$$P_k = p_{11,k} = \frac{\dim(\mathrm{Rep}_k)}{\dim G} \sum_{g \in G} r_{11}(g^{-1})\, g$$
Context: Gives the projector onto the $\mathrm{Rep}_k$ component of the path-space $V = \bigoplus_k \mathrm{Rep}_k^{\oplus m_k}$. Here $r_{\alpha\beta}(g)$ is the $(\alpha,\beta)$ matrix element of the real representation of $\mathrm{Rep}_k$ identified via the algorithm of arXiv:xu2021computation. Taking $\alpha = 1$ (first basis vector of $\mathrm{Rep}_k$) gives the projector $P_k$.
Why/How: Symmetry reduction via Invariant SDP: if the inner product is $G$-invariant, the positivity matrix $\mathcal{M}$ block-diagonalizes under the irreps of $G$. Each block has dimension $m_k \times m_k$ (multiplicity of $\mathrm{Rep}_k$ in $V$). This reduces the SDP from a single large matrix (e.g., $6505 \times 6505$) to many small ones (e.g., 20 blocks of $\leq 78$ dimensions in 3D at $L_\mathrm{max} = 16$), achieving order-of-magnitude speedups. Invariant group $G = B_d \times \mathbb{Z}_2$ for correlation matrices; subgroups for reflection matrices (see K.11).

(K.7) 3-loop perturbation theory, 4D, $N_c = \infty$ — TeX label `PLg`, §4:
$$u_P = 1 - \frac{\lambda}{8} - 0.005107\,\lambda^2 - 0.000794\,\lambda^3 + \mathcal{O}(\lambda^4)$$
Context: Valid in the weak-coupling phase $\lambda \ll 1$. Source: Alles et al. (arXiv:hep-lat/9803047, cited as \cite{Alles:1998is} in paper). Also cited are \cite{Bali:2014fea, Luscher:2014mka}.
Why/How: Perturbative expansion in the 't Hooft coupling $\lambda$. The coefficient $-1/8$ of the leading term arises from the one-loop plaquette integral over the gauge group; the subleading coefficients are pure numbers (no $N_c$ dependence at $N_c = \infty$). The upper bootstrap bound reproduces this formula even slightly beyond the phase transition point where PT is formally invalid.

(K.8) Strong-coupling expansion, 4D — TeX label `SCexp`, §4:
$$u_P = \frac{1}{\lambda} + \frac{4}{\lambda^5} + \frac{60}{\lambda^9} + \frac{136}{\lambda^{11}} + \frac{1092}{\lambda^{13}} + \mathcal{O}(\lambda^{-15})$$
Context: Valid in the strong-coupling phase $\lambda > \lambda_c \approx 2.9$. Source: Drouffe-Zuber (cited as \cite{Drouffe:1983fv} in paper).
Why/How: Strong-coupling (character) expansion in powers of $1/\lambda$. Only odd powers of $1/\lambda$ appear (no even powers); at this truncation the specific powers present are 1, 5, 9, 11, 13 — powers 3 and 7 are absent (they do not arise in the SC character expansion to this order). The coefficients grow. The leading $1/\lambda$ term is the single-plaquette result. The lower bootstrap bounds track this expansion in the strong-coupling phase.

(K.9) Block sizes after symmetry reduction — 3D, $L_\mathrm{max} = 16$ — §3.4 (body of paper):
$$38,\; 15,\; 25,\; 18,\; 62,\; 33,\; 68,\; 75,\; 56,\; 78,\quad 22,\; 18,\; 34,\; 15,\; 56,\; 33,\; 57,\; 76,\; 69,\; 73$$
Context: After selecting multiplets and applying Invariant SDP to the $6505 \times 6505$ correlation matrix for $0 \to 0$ paths at $L_\mathrm{max} = 16$ in 3D, the positivity constraint reduces to positivity of 20 blocks with the listed dimensions.
Why/How: The block sizes reflect the multiplicities $m_k$ of the irreps $\mathrm{Rep}_k$ of $B_3 \times \mathbb{Z}_2$ in the path space. Each block's SDP is independent. The maximum block size is 78, compared to 6505 for the unreduced matrix — a factor $\sim 83$ reduction in linear dimension, and a factor $\sim 500,000$ reduction in SDP variable count.

(K.10) 2D exact solution — TeX label `exact2D`, §4:
$$u_P = \begin{cases} 1 - \dfrac{\lambda}{4}, & \lambda \leq 2 \\ \dfrac{1}{\lambda}, & \lambda \geq 2 \end{cases}$$
Context: Exact at $N_c \to \infty$ in $D = 2$. Sources: Gross-Witten \cite{Gross:1980he} and Wadia \cite{Wadia:2012fr}; full loop average solution in Kazakov \cite{Kazakov:1981sb}.
Why/How: In $D = 2$, the lattice YM partition function reduces to independent plaquette integrals over $U(N_c)$. At $N_c = \infty$, the eigenvalue density of $U_P$ undergoes a third-order phase transition in $\lambda$ at $\lambda = 2$ (Gross-Witten-Wadia transition): $\partial^3 F/\partial\lambda^3$ is discontinuous while $F$, $\partial F/\partial\lambda$, and $\partial^2 F/\partial\lambda^2$ are continuous. For $\lambda < 2$ (weak coupling), the eigenvalue density is gapped; for $\lambda > 2$ (strong coupling), it is ungapped and $u_P = 1/\lambda$ matches the leading SC expansion. See Trap 5 for a discussion of what "third-order" means here.

(K.11) Invariant groups for positivity matrices — Table 1 of paper:

| Dimension | Hermitian Conjugation | Site/Link Reflection | Diagonal Reflection |
|-----------|----------------------|----------------------|---------------------|
| $D=2$     | $B_2 \times \mathbb{Z}_2$ | $\mathbb{Z}_2 \times \mathbb{Z}_2$ | $\mathbb{Z}_2 \times \mathbb{Z}_2$ |
| $D=3$     | $B_3 \times \mathbb{Z}_2$ | $B_2 \times \mathbb{Z}_2$ | $\mathbb{Z}_2^3$ |
| $D=4$     | $B_4 \times \mathbb{Z}_2$ | $B_3 \times \mathbb{Z}_2$ | $B_2 \times \mathbb{Z}_2^2$ |

Context: $B_d$ is the hyperoctahedral group (signed permutations of $d$ coordinates; the discrete symmetry group of the $d$-dimensional hypercube); it is the lattice analog of $O(d)$. $\mathbb{Z}_2$ is path-reversal (charge conjugation). Reflection planes reduce the symmetry group to a subgroup.
Why/How: The invariant group of the inner product determines which group to use for Invariant SDP. For correlation matrices ($0 \to 0$ paths), all lattice rotations and reflections plus path-reversal are symmetries: $G = B_d \times \mathbb{Z}_2$. For site/link reflection matrices, the reflection plane breaks $B_d$ to the subgroup preserving that plane: $B_{d-1} \times \mathbb{Z}_2$ (site/link) or $B_{d-2} \times \mathbb{Z}_2^2$ (diagonal in 4D).

(K.12) Loop equations for $L_\mathrm{max} = 8$ in 2D — TeX label `loop`, Supplementary §A (note: the TeX figure caption for the loop diagram reads "Loop equations for $\Lambda=4$", where $\Lambda=4$ refers to the perimeter of the elementary plaquette loop shown in the figure — the overall example cutoff is $L_\mathrm{max}=8$ as stated in the supplementary section heading):
$$-\mathcal{W}_2 + \mathcal{W}_3 + \mathcal{W}_4 - 1 = -\lambda \mathcal{W}_1$$
$$\mathcal{W}_2 - \mathcal{W}_4 - \mathcal{W}_5 + \mathcal{W}_6 = 0$$
Context: Two loop equations (one MMLE, one back-track LE) for the worked example. The six variables are the six independent closed Wilson loops $\mathcal{W}_1, \ldots, \mathcal{W}_6$ at $L_\mathrm{max} = 8$ in 2D; $\mathcal{W}_1 = u_P$ is the plaquette average. The second equation is linear (homogeneous) — it is an independent constraint from the back-track variation.
Why/How: At $L_\mathrm{max} = 8$ in 2D, all back-track LEs are linear (no quadratic RHS terms) so no convex relaxation is needed for this example. For higher $L_\mathrm{max}$ or higher $D$, nonlinear LEs appear and relaxation (K.5) is required.

(K.13) Symmetry-reduced positivity conditions for $L_\mathrm{max} = 8$ in 2D — TeX label `sym`, Supplementary §A:
$$\begin{pmatrix} 1 & \mathcal{W}_1 \\ \mathcal{W}_1 & \tfrac{1}{4}\mathcal{W}_2 + \tfrac{1}{8}\mathcal{W}_3 + \tfrac{1}{4}\mathcal{W}_4 + \tfrac{1}{8}\mathcal{W}_5 + \tfrac{1}{8}\mathcal{W}_6 + \tfrac{1}{8} \end{pmatrix} \succeq 0$$
$$-\tfrac{1}{4}\mathcal{W}_2 + \tfrac{1}{8}\mathcal{W}_3 - \tfrac{1}{4}\mathcal{W}_4 + \tfrac{1}{8}\mathcal{W}_5 + \tfrac{1}{8}\mathcal{W}_6 + \tfrac{1}{8} \geq 0$$
$$-\tfrac{1}{4}\mathcal{W}_3 + \tfrac{1}{4}\mathcal{W}_5 - \tfrac{1}{4}\mathcal{W}_6 + \tfrac{1}{4} \geq 0$$
$$\tfrac{1}{4}\mathcal{W}_2 - \tfrac{1}{8}\mathcal{W}_3 - \tfrac{1}{4}\mathcal{W}_4 - \tfrac{1}{8}\mathcal{W}_5 + \tfrac{1}{8}\mathcal{W}_6 + \tfrac{1}{8} \geq 0$$
$$-\tfrac{1}{4}\mathcal{W}_2 - \tfrac{1}{8}\mathcal{W}_3 + \tfrac{1}{4}\mathcal{W}_4 - \tfrac{1}{8}\mathcal{W}_5 + \tfrac{1}{8}\mathcal{W}_6 + \tfrac{1}{8} \geq 0$$
$$\tfrac{1}{4}\mathcal{W}_3 - \tfrac{1}{4}\mathcal{W}_5 - \tfrac{1}{4}\mathcal{W}_6 + \tfrac{1}{4} \geq 0$$
Context: After decomposing the $9 \times 9$ correlation matrix (eq. `pos` in paper) under $B_2 \times \mathbb{Z}_2$ — which has ten irreps total: $(A_1,\pm 1),(A_2,\pm 1),(B_1,\pm 1),(B_2,\pm 1),(E,\pm 1)$ (TeX Supplementary §A, lines 525–528) — into its six irrep blocks with nonzero multiplicity in this multiplet, $\{(A_1,+1),(B_2,+1),(E,+1),(B_1,-1),(A_2,-1),(E,-1)\}$, the positivity reduces to these six scalar/matrix conditions. (Four irreps — $(A_2,+1),(B_1,+1),(A_1,-1),(B_2,-1)$ — have zero multiplicity here and contribute no constraints.) These are equivalent to the full PSD condition on the $9 \times 9$ matrix but are far cheaper to enforce in the SDP.
Why/How: The block-diagonal form is purely group-theoretic; it does not change the set of feasible solutions, only the computational representation. At $\lambda = 2$: $0 \leq \mathcal{W}_1 \leq 0.69300$.

## Conventions

- **Gauge group**: $SU(N_c)$ in the body; bootstrap operates in the $N_c \to \infty$ ('t Hooft large-$N$) limit throughout. All WAs are normalized by $1/N_c$ (normalized trace $\mathrm{tr}/N_c$). The notation $\mathrm{tr}$ in the action (K.1) is the unnormalized trace; in the WA definition (K.2) it is explicitly $\mathrm{tr}/N_c$.

- **'t Hooft coupling**: $\lambda = g^2 N_c$ (bare lattice coupling). This is the coupling appearing in the Wilson action prefactor $N_c/\lambda$. It is NOT the string tension. Beware of papers that write $\beta = 2N_c/g^2 = 2N_c^2/\lambda$; Kazakov-Zheng do not use $\beta$. Some papers write the action as $(1/2g^2) \sum_P \mathrm{tr}(U_P + U_P^\dagger) = (N_c/\lambda) \sum_P \mathrm{Re}\,\mathrm{tr}\,U_P$; this differs from the KZ action $S = -(N_c/\lambda) \sum_P \mathrm{Re}\,\mathrm{tr}\,U_P$ by an overall sign. The sign difference is absorbed by the path-integral convention: some references use the partition function $Z = \int e^{+S_{\mathrm{positive}}}$ (action positive-definite at weak coupling), while KZ implicitly use $Z = \int e^{S}$ with $S < 0$ at weak coupling. These conventions yield identical physics, but numerical values of $S$ have opposite signs — do not conflate them.

- **Plaquette average**: $u_P = \frac{1}{N_c} \langle \mathrm{tr}\, U_P \rangle = W[\text{single plaquette}]$. The definition carries no explicit Re; $u_P$ is real at $N_c \to \infty$ by charge conjugation symmetry (TeX line 183). Do not write $u_P = \frac{1}{N_c}\mathrm{Re}\langle \mathrm{tr}\, U_P \rangle$; that is a consequence of the symmetry, not part of the definition.

- **Loop orientation**: $U_P$ includes both orientations in the sum over plaquettes $\sum_P$, so the action is real. Wilson loops $W[C]$ carry a direction; reversing $C$ gives the complex conjugate $W[C^{-1}] = W[C]^*$. At large $N_c$ all WAs are real (charge conjugation symmetry), so $W[C^{-1}] = W[C]$.

- **Metric**: Euclidean lattice; no metric signature issue. All indices are spatial.

- **Reflection positivity terminology**: The paper follows Osterwalder-Seiler \cite{OSTERWALDER1978440} and Montvay-Munster \cite{montvay1997quantum} for the three lattice reflection types.

- **No existing project CONVENTIONS.md** was found at `GPD/CONVENTIONS.md`. Convention clashes between this paper and K-001 (Lin BFSS bootstrap) are flagged in the Traps section below.

**Convention clashes vs. K-001 (Lin BFSS bootstrap)**:

- K-001 uses a Minkowski-like BFSS Hamiltonian with coupling $g^2$ appearing explicitly; Kazakov-Zheng use a Euclidean lattice action with 't Hooft coupling $\lambda = g^2 N_c$. The normalization $1/N_c$ vs. $1/N$ of the trace differs in presentation style (K-001 uses $\mathrm{Tr}$ for unnormalized and $\mathrm{tr}$ for normalized; Kazakov-Zheng use $\mathrm{tr}$ for both, distinguished by context).

- The "bootstrap variables" in K-001 are single-trace quantum-mechanical correlators at fixed energy; in this paper they are single-trace Wilson loop averages in the Euclidean path integral. The SDP positivity structure is directly analogous.

## Derivation Sketches

### Makeenko-Migdal loop equations (K.3)

Starting from the partition function $Z = \int \prod_l dU_l\, e^{-S}$ with $S$ from (K.1), apply the SD shift $U_l \to U_l(1 + i\epsilon t^a)$ for each generator $t^a$ of $SU(N_c)$. The measure is invariant; differentiating the integrand gives $\langle \frac{\delta S}{\delta \epsilon}\,\mathcal{O} \rangle - \langle \frac{\delta \mathcal{O}}{\delta \epsilon} \rangle = 0$ for any operator $\mathcal{O}$. Taking $\mathcal{O}$ to be a Wilson loop that contains the link $l$ and summing over generators $a$ (using $t^a_{ij} t^a_{kl} = \delta_{il}\delta_{jk} - (1/N_c)\delta_{ij}\delta_{kl}$) produces the MMLE. At $N_c \to \infty$ the $1/N_c$ term drops and the right-hand side factorizes into a product of two WAs. The LHS is the "loop derivative" — the Schwinger-Dyson operator on loop space.

### Back-track loop equations

A "back-track" path is a path of the form $\ldots \to x \to y \to x \to \ldots$ appended to a vertex of the Wilson loop. When inserted into the loop, a back-track is the identity ($U_l U_l^{-1} = 1$). However, the SD variation $U_l \to U_l(1+i\epsilon)$ acts on the link $U_l$ in the back-track, generating a nontrivial contribution to the LE. The result is a new LE involving WAs of the loop with the back-track excised plus nonlinear RHS terms from self-intersections. These back-track LEs are independent of the MMLE and constitute more than 80% of all LEs at practical $L_\mathrm{max}$.

### Convex relaxation

The nonlinear RHS of (K.3) involves products $W[C_{ll'}] W[C_{l'l}]$. Introduce $Q_{ij} = W_i W_j$ as a new matrix variable (where $W_i$ indexes all inequivalent WAs). The exact constraint $\mathrm{rank}(Q - WW^T) = 0$ is non-convex. By Schur complement, $\begin{pmatrix} 1 & W^T \\ W & Q \end{pmatrix} \succeq 0$ is equivalent to $Q - WW^T \succeq 0$, which is convex (an LMI). This replaces every nonlinear LE with a linear constraint (using $Q_{ij}$ in place of $W_i W_j$) plus the global LMI. The resulting problem is an SDP: minimize/maximize $u_P$ subject to linear LEs (using $Q$) and LMI constraints from (K.4) and (K.5).

### Invariant SDP / symmetry reduction

If the inner product $\langle \mathcal{O}_i^\dagger \mathcal{O}_j \rangle$ is $G$-invariant, the matrix $\mathcal{M}$ commutes with the group action: $[\mathcal{M}, \rho(g)] = 0$ for all $g \in G$ and all representations $\rho$ of $G$ on the path space. By Schur's lemma, $\mathcal{M}$ is block-diagonal in the irrep basis. To find the projectors explicitly: (1) use GAP software to identify all irreps of $G$; (2) find equivalent real representations; (3) apply the projector formula (K.6). The result is a set of independent small SDP constraints, one per irrep, that are collectively equivalent to the original large SDP.

## Connections

- **Related to K-001 (Lin 2023, BFSS bootstrap)**: Lin's paper applies the same bootstrap philosophy — positivity matrices + Schwinger-Dyson (virial theorem) constraints + SDP — to the BFSS matrix quantum mechanics (continuum, Minkowski). Kazakov-Zheng apply an extended version (with convex relaxation + symmetry reduction + reflection positivity) to lattice YM. The structural analogy is direct: WAs $\leftrightarrow$ single-trace correlators; MMLE $\leftrightarrow$ virial/trace identities; correlation matrix $\leftrightarrow$ positivity matrix $\mathcal{M}_2$; convex relaxation $\leftrightarrow$ not present in K-001 (Lin uses a smaller and simpler SDP). Kazakov-Zheng is the methodologically more advanced paper.

- **Methodological predecessor**: Kazakov-Zheng cite their own arXiv:2104.13672 (matrix bootstrap with relaxation), which established the convex relaxation + Invariant SDP approach for multi-matrix models. That paper is the direct precursor; the current paper extends it to LGT.

- **Anderson-Kruczenski**: arXiv:1612.08760, arXiv:1811.06171 — the pioneering LYM bootstrap papers. Kazakov-Zheng explicitly improve upon these by adding reflection positivity, convex relaxation, and symmetry reduction.

- **Gross-Witten-Wadia transition**: The 2D exact solution (K.10) is the GWW transition — the large-$N$ phase transition in the eigenvalue density of unitary matrix models. This transition is NOT present at finite $N_c$. It is relevant for BFSS as an exactly solvable benchmark of similar structure.

- **BFSS project relevance**: The techniques developed here — SDP-based bounds on gauge-invariant observables via loop-operator Schwinger-Dyson equations, reflection positivity from symmetries, convex relaxation, Invariant SDP — are directly applicable to the BFSS bootstrap program once the loop-operator language is set up for the BFSS matrix quantum mechanics. The paper demonstrates that the approach scales to $\sim 10^5$ constraints and $\sim 10^3$-dimensional matrices on a single workstation.

## Open Questions

- What is the systematic error from truncating to $L_\mathrm{max} = 16$? The paper estimates the physical scale window as $2 \lesssim l_{ph}/a_L \lesssim 6$ for $L_\mathrm{max} = 16$, but no quantitative extrapolation in $L_\mathrm{max}$ is given.

- Can the method reach $L_\mathrm{max} = 20$ or $L_\mathrm{max} = 24$ on supercomputer hardware? The paper states this expectation but leaves it to future work.

- Can one extract glueball masses or the string tension from the bootstrap? The paper mentions connected correlators of small Wilson loops as a route to glueball masses but does not pursue it.

- Can the method be extended to finite $N_c$ (e.g., $N_c = 3$)? The factorization that closes the LEs on single-trace WAs is a large-$N$ property; at finite $N_c$, the LEs involve multi-trace operators. The paper notes that $1/N_c$ corrections satisfy linear LEs with coefficients from the large-$N$ solution.

- Can quarks (dynamical fermions) be included? At $N_c = \infty$ there are no internal fermion loops; the paper speculates that quark condensate and hadron masses could be obtained by summing WAs with spinorial factors.

- How tight is the convex relaxation? The gap between the SDP feasible set and the exact (rank-1) set is not quantified; it is only known empirically to shrink as $L_\mathrm{max}$ increases.

- Can the method capture the 4D deconfinement phase transition sharply? At present the bounds near $\lambda_c \approx 2.9$ are not tight enough to characterize the transition quantitatively.

## Traps and Subtleties

1. **'t Hooft coupling convention**: $\lambda = g^2 N_c$ in this paper. It is NOT the string tension. Some papers write the Wilson action as $(1/(2g^2)) \sum_P \mathrm{tr}(U_P + U_P^\dagger)$ or use $\beta = 2N_c/g^2 = 2N_c^2/\lambda$. The relation is $\beta = 2N_c^2/\lambda$ (e.g., for $SU(3)$: $\beta_{\rm lat} = 6/g^2 = 6N_c/\lambda$). Always check which convention a paper uses before comparing numerical values of $\lambda$ or $\beta$.

2. **Loop length cutoff $L_\mathrm{max}$ is an IR cutoff, NOT a UV cutoff**: $L_\mathrm{max}$ bounds the length of loops entering the bootstrap, which translates to a bound on the spatial extent of the Wilson loops probed. A loop of length $L$ probes physics at scale $L a_L$ in lattice units. Increasing $L_\mathrm{max}$ accesses longer-range physics, not shorter-distance physics. The continuum (UV) limit is $a_L \to 0$ at fixed physics — a separate issue not addressed in this paper.

3. **Back-track paths are NOT zero**: A back-track loop $U_l U_l^\dagger = 1$ inserted into a Wilson loop is the identity element and leaves the WA unchanged. However, the Schwinger-Dyson variation of the link $U_l$ inside the back-track is NOT zero — it produces a non-trivial LE. Confusing "inserting a back-track does nothing to the loop" with "the back-track LE is trivial" is wrong. Back-track LEs are independent constraints and constitute the majority of all LEs at practical $L_\mathrm{max}$.

4. **Convex relaxation: the SDP may have non-physical solutions**: The relaxation matrix $\begin{pmatrix} 1 & W^T \\ W & Q \end{pmatrix} \succeq 0$ has rank 1 if and only if $Q_{ij} = W_i W_j$. SDP solutions with $\mathrm{rank} > 1$ are feasible for the relaxed SDP but do not correspond to genuine WA configurations. The upper and lower bounds on $u_P$ from the SDP are rigorous (they bound the true solution from outside), but one cannot read off a unique WA configuration from the SDP dual solution.

5. **2D phase transition at $\lambda = 2$ is a large-$N$ transition**: The GWW transition (K.10) is a third-order phase transition as a function of the coupling $\lambda$ at $N_c = \infty$: the free energy $F(\lambda)$ has a discontinuity in $\partial^3 F/\partial\lambda^3$ at $\lambda = 2$, while lower derivatives are continuous. ("Third-order" refers to the order of the derivative that first becomes discontinuous — it is a statement about $\lambda$-dependence, not about the $1/N_c$ expansion.) The transition is NOT present at finite $N_c$ — it is a large-$N$ artifact caused by the change in topology of the eigenvalue density of $U_P$ (from a gapped distribution for $\lambda < 2$ to an ungapped one for $\lambda > 2$). Do not confuse it with the first-order phase transition at $\lambda_c \approx 2.9$ in 4D, which is a different (lattice-artifact Bulk) transition believed to survive in the large-$N_c$ limit and to be related to the deconfinement transition.

6. **Normalization of trace**: In (K.1), $\mathrm{tr}$ is the unnormalized trace (sum of eigenvalues). In (K.2), the WA uses $\mathrm{tr}/N_c$ (normalized). The plaquette average $u_P = \frac{1}{N_c}\langle \mathrm{tr}\, U_P \rangle$ is normalized. When plugging expressions for $u_P$ into the action, care is needed: $S = -(N_c/\lambda) \sum_P \mathrm{Re}\,\mathrm{tr}\, U_P = -(N_c^2/\lambda) \sum_P \mathrm{Re}\, u_P$, picking up a factor of $N_c$.

7. **Symmetry reduction requires $G$-invariance of the inner product**: The Invariant SDP reduction (K.6) is only valid if the group $G$ genuinely acts as symmetries of the inner product. For the correlation matrix, $G = B_d \times \mathbb{Z}_2$ is an exact symmetry of the Euclidean Wilson action and measure, so this holds. For reflection matrices, the corresponding subgroup must leave the reflection plane invariant. If any symmetry is broken (e.g., by boundary conditions or anisotropy), the block-diagonal structure is lost.

8. **Selection of multiplets**: The paper notes that some WAs (e.g., the $4 \times 4$ square Wilson loop at $L_\mathrm{max} = 16$) are not related to other WAs by the LEs and are considered relatively unimportant; only the most important multiplets are included. This is a practical approximation, not an exact reduction — including more multiplets can only improve (tighten) the bounds.

9. **CPU scaling**: Each 4D data point at $L_\mathrm{max} = 16$ requires approximately 20 hours on a single workstation. The 3D case requires approximately 0.5 hours. The jump from $L_\mathrm{max} = 16$ to $L_\mathrm{max} = 20$ is expected to require supercomputer resources. This practical constraint is relevant for any BFSS bootstrap attempt using analogous methods.
