# G3-h -- the window placements' "measure both" switches, measured through the window-flat read (bank2 fulllead RUN)

Grid: arm_cap {budget, x} x z_deep {slide, order, order_window} x seat_empty_axis {allow, deny}; centre_scope both, strict judgement, growth z_reserved, seat_key unit_sid, level mid, padding one (592 windows, 292 pairs) in every cell. Read: slide_flat.ask_flat, members = the first member of each growth, search budget 512/64, both seats of a shared unit, read order qcount_first, windows read: fast 4 / standard 10, tier RUN, the per-axis labels attached (labels only), evidence plain | window. Grading: t9 scorer, as g3/s1flat/summarize_flat.py (gold in a candidate = the gold is a substring of one word of one candidate; single = exactly one candidate entry; list = at least two). Times are wall seconds per question with 6 worker processes at the load stated in the meta files (not comparable to a quiet machine). The cell budget / slide / allow is the G3-f row; the check against the G3-f records is the last section.

Under the combined list (G3-g2) a window-only single entry never ANSWERs: the `single right / wrong` columns below are the flat grader's (one candidate), and the same questions are lists of one entry in the combined list.

## intra2 (n = 69), fast, evidence plain

| arm_cap / z_deep / seat_empty | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size: entries median / max | words in the list median / max | s/question median (max) |
|---|---|---|---|---|---|---|---|---|---|
| budget / slide / allow | 9 (13%) | 3 | 5 | 6 | 11 | 44 | 2.0 / 6 | 12.0 / 32 | 1.41 (13.42) |
| budget / slide / deny | 9 (13%) | 3 | 5 | 6 | 11 | 44 | 2.0 / 6 | 12.0 / 32 | 1.47 (14.54) |
| budget / order / allow | 7 (10%) | 2 | 7 | 5 | 14 | 41 | 3.0 / 8 | 13.0 / 39 | 3.61 (16.53) |
| budget / order / deny | 7 (10%) | 2 | 7 | 5 | 14 | 41 | 3.0 / 8 | 13.0 / 39 | 3.69 (16.86) |
| budget / order_window / allow | 9 (13%) | 3 | 4 | 6 | 10 | 46 | 3.0 / 10 | 13.5 / 50 | 3.37 (15.88) |
| budget / order_window / deny | 9 (13%) | 3 | 4 | 6 | 10 | 46 | 3.0 / 10 | 13.5 / 50 | 3.30 (15.91) |
| x / slide / allow | 10 (14%) | 4 | 6 | 6 | 8 | 45 | 2.0 / 6 | 12.0 / 32 | 1.46 (14.45) |
| x / slide / deny | 10 (14%) | 4 | 6 | 6 | 8 | 45 | 2.0 / 6 | 12.0 / 32 | 1.37 (14.46) |
| x / order / allow | 11 (16%) | 4 | 5 | 7 | 10 | 43 | 3.0 / 9 | 15.0 / 63 | 2.00 (15.49) |
| x / order / deny | 11 (16%) | 4 | 5 | 7 | 10 | 43 | 3.0 / 9 | 15.0 / 63 | 1.95 (15.32) |
| x / order_window / allow | 10 (14%) | 4 | 6 | 6 | 9 | 44 | 3.0 / 7 | 16.0 / 46 | 2.18 (15.17) |
| x / order_window / deny | 10 (14%) | 4 | 6 | 6 | 9 | 44 | 3.0 / 7 | 16.0 / 46 | 1.92 (14.64) |

## unans (n = 25), fast, evidence plain

| arm_cap / z_deep / seat_empty | abstained (no candidate) | list only | single answer (confident wrong) | list size: entries median / max |
|---|---|---|---|---|
| budget / slide / allow | 18 | 2 | 5 | 3.5 / 5 |
| budget / slide / deny | 18 | 2 | 5 | 3.5 / 5 |
| budget / order / allow | 16 | 3 | 6 | 3.0 / 5 |
| budget / order / deny | 16 | 3 | 6 | 3.0 / 5 |
| budget / order_window / allow | 17 | 3 | 5 | 3.0 / 5 |
| budget / order_window / deny | 17 | 3 | 5 | 3.0 / 5 |
| x / slide / allow | 19 | 2 | 4 | 2.5 / 3 |
| x / slide / deny | 19 | 2 | 4 | 2.5 / 3 |
| x / order / allow | 18 | 3 | 4 | 2.0 / 3 |
| x / order / deny | 18 | 3 | 4 | 2.0 / 3 |
| x / order_window / allow | 18 | 3 | 4 | 2.0 / 7 |
| x / order_window / deny | 18 | 3 | 4 | 2.0 / 7 |

## intra2 (n = 69), fast, evidence window

| arm_cap / z_deep / seat_empty | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size: entries median / max | words in the list median / max | s/question median (max) |
|---|---|---|---|---|---|---|---|---|---|
| budget / slide / allow | 19 (28%) | 5 | 17 | 14 | 15 | 18 | 3.0 / 6 | 16.0 / 36 | 1.03 (13.18) |
| budget / slide / deny | 19 (28%) | 5 | 17 | 14 | 15 | 18 | 3.0 / 6 | 16.0 / 36 | 1.17 (13.89) |
| budget / order / allow | 20 (29%) | 1 | 14 | 19 | 17 | 18 | 4.0 / 15 | 19.5 / 102 | 2.14 (13.74) |
| budget / order / deny | 20 (29%) | 1 | 14 | 19 | 17 | 18 | 4.0 / 15 | 19.5 / 102 | 2.21 (14.07) |
| budget / order_window / allow | 22 (32%) | 3 | 7 | 19 | 19 | 21 | 4.0 / 17 | 18.0 / 90 | 1.95 (13.93) |
| budget / order_window / deny | 22 (32%) | 3 | 7 | 19 | 19 | 21 | 4.0 / 17 | 18.0 / 90 | 1.79 (13.41) |
| x / slide / allow | 20 (29%) | 6 | 18 | 14 | 14 | 17 | 2.0 / 9 | 14.5 / 52 | 1.11 (14.31) |
| x / slide / deny | 20 (29%) | 6 | 18 | 14 | 14 | 17 | 2.0 / 9 | 14.5 / 52 | 1.08 (14.03) |
| x / order / allow | 23 (33%) | 6 | 8 | 17 | 16 | 22 | 2.0 / 14 | 14.0 / 96 | 1.68 (13.07) |
| x / order / deny | 23 (33%) | 6 | 8 | 17 | 16 | 22 | 2.0 / 14 | 14.0 / 96 | 1.60 (12.70) |
| x / order_window / allow | 21 (30%) | 6 | 11 | 15 | 15 | 22 | 3.0 / 8 | 15.5 / 57 | 1.66 (12.61) |
| x / order_window / deny | 21 (30%) | 6 | 11 | 15 | 15 | 22 | 3.0 / 8 | 15.5 / 57 | 1.52 (11.10) |

## unans (n = 25), fast, evidence window

| arm_cap / z_deep / seat_empty | abstained (no candidate) | list only | single answer (confident wrong) | list size: entries median / max |
|---|---|---|---|---|
| budget / slide / allow | 6 | 9 | 10 | 3.0 / 6 |
| budget / slide / deny | 6 | 9 | 10 | 3.0 / 6 |
| budget / order / allow | 3 | 14 | 8 | 3.5 / 8 |
| budget / order / deny | 3 | 14 | 8 | 3.5 / 8 |
| budget / order_window / allow | 2 | 15 | 8 | 3.0 / 8 |
| budget / order_window / deny | 2 | 15 | 8 | 3.0 / 8 |
| x / slide / allow | 7 | 11 | 7 | 3.0 / 6 |
| x / slide / deny | 7 | 11 | 7 | 3.0 / 6 |
| x / order / allow | 8 | 12 | 5 | 4.0 / 14 |
| x / order / deny | 8 | 12 | 5 | 4.0 / 14 |
| x / order_window / allow | 8 | 12 | 5 | 4.5 / 14 |
| x / order_window / deny | 8 | 12 | 5 | 4.5 / 14 |

## intra2 (n = 69), standard, evidence plain

| arm_cap / z_deep / seat_empty | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size: entries median / max | words in the list median / max | s/question median (max) |
|---|---|---|---|---|---|---|---|---|---|
| budget / slide / allow | 10 (14%) | 0 | 10 | 10 | 18 | 31 | 3.0 / 10 | 15.5 / 50 | 3.65 (22.35) |
| budget / slide / deny | 10 (14%) | 0 | 10 | 10 | 18 | 31 | 3.0 / 10 | 15.5 / 50 | 3.96 (24.44) |
| budget / order / allow | 8 (12%) | 1 | 7 | 7 | 27 | 27 | 4.0 / 16 | 20.0 / 88 | 9.22 (30.86) |
| budget / order / deny | 8 (12%) | 1 | 7 | 7 | 27 | 27 | 4.0 / 16 | 20.0 / 88 | 9.05 (30.09) |
| budget / order_window / allow | 10 (14%) | 2 | 5 | 8 | 27 | 27 | 4.0 / 14 | 19.0 / 71 | 8.44 (32.42) |
| budget / order_window / deny | 10 (14%) | 2 | 5 | 8 | 27 | 27 | 4.0 / 14 | 19.0 / 71 | 8.11 (32.64) |
| x / slide / allow | 11 (16%) | 1 | 11 | 10 | 15 | 32 | 4.0 / 9 | 19.0 / 46 | 3.90 (24.22) |
| x / slide / deny | 11 (16%) | 1 | 11 | 10 | 15 | 32 | 4.0 / 9 | 19.0 / 46 | 3.80 (23.50) |
| x / order / allow | 12 (17%) | 3 | 11 | 9 | 18 | 28 | 3.0 / 13 | 21.0 / 81 | 4.65 (28.62) |
| x / order / deny | 12 (17%) | 3 | 11 | 9 | 18 | 28 | 3.0 / 13 | 21.0 / 81 | 4.56 (27.50) |
| x / order_window / allow | 11 (16%) | 2 | 12 | 9 | 18 | 28 | 3.0 / 11 | 21.0 / 64 | 4.28 (26.13) |
| x / order_window / deny | 11 (16%) | 2 | 12 | 9 | 18 | 28 | 3.0 / 11 | 21.0 / 64 | 4.20 (24.93) |

## unans (n = 25), standard, evidence plain

| arm_cap / z_deep / seat_empty | abstained (no candidate) | list only | single answer (confident wrong) | list size: entries median / max |
|---|---|---|---|---|
| budget / slide / allow | 16 | 5 | 4 | 2.0 / 5 |
| budget / slide / deny | 16 | 5 | 4 | 2.0 / 5 |
| budget / order / allow | 13 | 7 | 5 | 4.0 / 5 |
| budget / order / deny | 13 | 7 | 5 | 4.0 / 5 |
| budget / order_window / allow | 14 | 5 | 6 | 4.0 / 5 |
| budget / order_window / deny | 14 | 5 | 6 | 4.0 / 5 |
| x / slide / allow | 15 | 7 | 3 | 3.0 / 3 |
| x / slide / deny | 15 | 7 | 3 | 3.0 / 3 |
| x / order / allow | 15 | 6 | 4 | 3.5 / 4 |
| x / order / deny | 15 | 6 | 4 | 3.5 / 4 |
| x / order_window / allow | 15 | 5 | 5 | 3.0 / 7 |
| x / order_window / deny | 15 | 5 | 5 | 3.0 / 7 |

## intra2 (n = 69), standard, evidence window

| arm_cap / z_deep / seat_empty | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size: entries median / max | words in the list median / max | s/question median (max) |
|---|---|---|---|---|---|---|---|---|---|
| budget / slide / allow | 21 (30%) | 2 | 12 | 19 | 28 | 8 | 4.0 / 11 | 22.0 / 58 | 3.02 (18.15) |
| budget / slide / deny | 21 (30%) | 2 | 12 | 19 | 28 | 8 | 4.0 / 11 | 22.0 / 58 | 3.16 (18.62) |
| budget / order / allow | 21 (30%) | 0 | 8 | 21 | 31 | 9 | 5.0 / 24 | 29.0 / 157 | 5.60 (35.20) |
| budget / order / deny | 21 (30%) | 0 | 8 | 21 | 31 | 9 | 5.0 / 24 | 29.0 / 157 | 5.40 (34.48) |
| budget / order_window / allow | 24 (35%) | 2 | 2 | 22 | 32 | 11 | 6.0 / 17 | 33.5 / 94 | 5.32 (26.38) |
| budget / order_window / deny | 24 (35%) | 2 | 2 | 22 | 32 | 11 | 6.0 / 17 | 33.5 / 94 | 5.08 (25.18) |
| x / slide / allow | 22 (32%) | 3 | 10 | 19 | 28 | 9 | 4.0 / 13 | 19.0 / 61 | 3.18 (19.05) |
| x / slide / deny | 22 (32%) | 3 | 10 | 19 | 28 | 9 | 4.0 / 13 | 19.0 / 61 | 3.07 (18.70) |
| x / order / allow | 24 (35%) | 5 | 6 | 19 | 28 | 11 | 4.0 / 24 | 24.0 / 156 | 3.93 (23.13) |
| x / order / deny | 24 (35%) | 5 | 6 | 19 | 28 | 11 | 4.0 / 24 | 24.0 / 156 | 3.70 (19.88) |
| x / order_window / allow | 22 (32%) | 4 | 6 | 18 | 30 | 11 | 5.0 / 17 | 30.0 / 115 | 3.71 (22.66) |
| x / order_window / deny | 22 (32%) | 4 | 6 | 18 | 30 | 11 | 5.0 / 17 | 30.0 / 115 | 3.34 (20.25) |

## unans (n = 25), standard, evidence window

| arm_cap / z_deep / seat_empty | abstained (no candidate) | list only | single answer (confident wrong) | list size: entries median / max |
|---|---|---|---|---|
| budget / slide / allow | 4 | 12 | 9 | 3.0 / 11 |
| budget / slide / deny | 4 | 12 | 9 | 3.0 / 11 |
| budget / order / allow | 3 | 16 | 6 | 4.5 / 13 |
| budget / order / deny | 3 | 16 | 6 | 4.5 / 13 |
| budget / order_window / allow | 2 | 17 | 6 | 5.0 / 15 |
| budget / order_window / deny | 2 | 17 | 6 | 5.0 / 15 |
| x / slide / allow | 5 | 13 | 7 | 3.0 / 11 |
| x / slide / deny | 5 | 13 | 7 | 3.0 / 11 |
| x / order / allow | 6 | 15 | 4 | 4.0 / 14 |
| x / order / deny | 6 | 15 | 4 | 4.0 / 14 |
| x / order_window / allow | 6 | 15 | 4 | 5.0 / 14 |
| x / order_window / deny | 6 | 15 | 4 | 5.0 / 14 |

## The grid at a glance: gold in a candidate (of 69) | unans abstained / list / single wrong (of 25), per run

| arm_cap / z_deep / seat_empty | fast plain gold | fast plain unans | fast window gold | fast window unans | standard plain gold | standard plain unans | standard window gold | standard window unans |
|---|---|---|---|---|---|---|---|---|
| budget / slide / allow | 9 | 18 / 2 / 5 | 19 | 6 / 9 / 10 | 10 | 16 / 5 / 4 | 21 | 4 / 12 / 9 |
| budget / slide / deny | 9 | 18 / 2 / 5 | 19 | 6 / 9 / 10 | 10 | 16 / 5 / 4 | 21 | 4 / 12 / 9 |
| budget / order / allow | 7 | 16 / 3 / 6 | 20 | 3 / 14 / 8 | 8 | 13 / 7 / 5 | 21 | 3 / 16 / 6 |
| budget / order / deny | 7 | 16 / 3 / 6 | 20 | 3 / 14 / 8 | 8 | 13 / 7 / 5 | 21 | 3 / 16 / 6 |
| budget / order_window / allow | 9 | 17 / 3 / 5 | 22 | 2 / 15 / 8 | 10 | 14 / 5 / 6 | 24 | 2 / 17 / 6 |
| budget / order_window / deny | 9 | 17 / 3 / 5 | 22 | 2 / 15 / 8 | 10 | 14 / 5 / 6 | 24 | 2 / 17 / 6 |
| x / slide / allow | 10 | 19 / 2 / 4 | 20 | 7 / 11 / 7 | 11 | 15 / 7 / 3 | 22 | 5 / 13 / 7 |
| x / slide / deny | 10 | 19 / 2 / 4 | 20 | 7 / 11 / 7 | 11 | 15 / 7 / 3 | 22 | 5 / 13 / 7 |
| x / order / allow | 11 | 18 / 3 / 4 | 23 | 8 / 12 / 5 | 12 | 15 / 6 / 4 | 24 | 6 / 15 / 4 |
| x / order / deny | 11 | 18 / 3 / 4 | 23 | 8 / 12 / 5 | 12 | 15 / 6 / 4 | 24 | 6 / 15 / 4 |
| x / order_window / allow | 10 | 18 / 3 / 4 | 21 | 8 / 12 / 5 | 11 | 15 / 5 / 5 | 22 | 6 / 15 / 4 |
| x / order_window / deny | 10 | 18 / 3 / 4 | 21 | 8 / 12 / 5 | 11 | 15 / 5 / 5 | 22 | 6 / 15 / 4 |

## One factor at a time: the sum over the other factors' cells (gold in a candidate summed over the cells of the factor value; answerable single wrong summed; unans abstained and unans single wrong summed). arm_cap and z_deep over the ALLOW cells only (deny seats the same units, so its cells would only double the sums); seat_empty over all twelve

| factor = value | cells | fast plain: gold / single wrong / unans abst. / unans single | fast window: gold / single wrong / unans abst. / unans single | standard plain: gold / single wrong / unans abst. / unans single | standard window: gold / single wrong / unans abst. / unans single |
|---|---|---|---|---|---|
| arm_cap = budget | 3 | 25 / 16 / 51 / 16 | 61 / 38 / 11 / 26 | 28 / 22 / 43 / 15 | 66 / 22 / 9 / 21 |
| arm_cap = x | 3 | 31 / 17 / 55 / 12 | 64 / 37 / 23 / 17 | 34 / 34 / 45 / 12 | 68 / 22 / 17 / 15 |
| z_deep = slide | 2 | 19 / 11 / 37 / 9 | 39 / 35 / 13 / 17 | 21 / 21 / 31 / 7 | 43 / 22 / 9 / 16 |
| z_deep = order | 2 | 18 / 12 / 34 / 10 | 43 / 22 / 11 / 13 | 20 / 18 / 28 / 9 | 45 / 14 / 9 / 10 |
| z_deep = order_window | 2 | 19 / 10 / 35 / 9 | 43 / 18 / 10 / 13 | 21 / 17 / 29 / 11 | 46 / 8 / 8 / 10 |
| seat_empty = allow | 6 | 56 / 33 / 106 / 28 | 125 / 75 / 34 / 43 | 62 / 56 / 88 / 27 | 134 / 44 / 26 / 36 |
| seat_empty = deny | 6 | 56 / 33 / 106 / 28 | 125 / 75 / 34 / 43 | 62 / 56 / 88 / 27 | 134 / 44 / 26 / 36 |

## Which answerable questions have the gold in a candidate, against the reference cell budget / slide / allow (G3-f's configuration): gained / lost question ids

| run | cell | gold | gained | lost |
|---|---|---|---|---|
| fast plain | budget / slide / deny | 9 | - | - |
| fast plain | budget / order / allow | 7 | I2-035 | I2-037, R2-I013, R2-I018 |
| fast plain | budget / order / deny | 7 | I2-035 | I2-037, R2-I013, R2-I018 |
| fast plain | budget / order_window / allow | 9 | I2-029, I2-035 | R2-I013, R2-I018 |
| fast plain | budget / order_window / deny | 9 | I2-029, I2-035 | R2-I013, R2-I018 |
| fast plain | x / slide / allow | 10 | R2-I001 | - |
| fast plain | x / slide / deny | 10 | R2-I001 | - |
| fast plain | x / order / allow | 11 | I2-021, I2-022, I2-023, I2-035, R2-I001 | I2-037, R2-I013, R2-I018 |
| fast plain | x / order / deny | 11 | I2-021, I2-022, I2-023, I2-035, R2-I001 | I2-037, R2-I013, R2-I018 |
| fast plain | x / order_window / allow | 10 | I2-023, I2-029, I2-035, R2-I001 | I2-037, R2-I013, R2-I018 |
| fast plain | x / order_window / deny | 10 | I2-023, I2-029, I2-035, R2-I001 | I2-037, R2-I013, R2-I018 |
| fast window | budget / slide / deny | 19 | - | - |
| fast window | budget / order / allow | 20 | I2-012, I2-024, I2-027, I2-029, I2-034, I2-035, I2-042 | I2-004, I2-006, I2-022, I2-037, R2-I013, R2-I018 |
| fast window | budget / order / deny | 20 | I2-012, I2-024, I2-027, I2-029, I2-034, I2-035, I2-042 | I2-004, I2-006, I2-022, I2-037, R2-I013, R2-I018 |
| fast window | budget / order_window / allow | 22 | I2-012, I2-024, I2-025, I2-027, I2-029, I2-034, I2-035, I2-042 | I2-004, I2-006, I2-022, R2-I013, R2-I018 |
| fast window | budget / order_window / deny | 22 | I2-012, I2-024, I2-025, I2-027, I2-029, I2-034, I2-035, I2-042 | I2-004, I2-006, I2-022, R2-I013, R2-I018 |
| fast window | x / slide / allow | 20 | I2-023, R2-I001 | R2-I010 |
| fast window | x / slide / deny | 20 | I2-023, R2-I001 | R2-I010 |
| fast window | x / order / allow | 23 | I2-012, I2-021, I2-023, I2-024, I2-027, I2-034, I2-035, I2-042, R2-I001 | I2-004, I2-006, R2-I010, R2-I013, R2-I018 |
| fast window | x / order / deny | 23 | I2-012, I2-021, I2-023, I2-024, I2-027, I2-034, I2-035, I2-042, R2-I001 | I2-004, I2-006, R2-I010, R2-I013, R2-I018 |
| fast window | x / order_window / allow | 21 | I2-021, I2-023, I2-024, I2-025, I2-027, I2-034, I2-035, I2-042, R2-I001 | I2-004, I2-006, I2-013, I2-022, R2-I010, R2-I013, R2-I018 |
| fast window | x / order_window / deny | 21 | I2-021, I2-023, I2-024, I2-025, I2-027, I2-034, I2-035, I2-042, R2-I001 | I2-004, I2-006, I2-013, I2-022, R2-I010, R2-I013, R2-I018 |
| standard plain | budget / slide / deny | 10 | - | - |
| standard plain | budget / order / allow | 8 | I2-035 | I2-037, R2-I013, R2-I018 |
| standard plain | budget / order / deny | 8 | I2-035 | I2-037, R2-I013, R2-I018 |
| standard plain | budget / order_window / allow | 10 | I2-029, I2-035 | R2-I013, R2-I018 |
| standard plain | budget / order_window / deny | 10 | I2-029, I2-035 | R2-I013, R2-I018 |
| standard plain | x / slide / allow | 11 | R2-I001 | - |
| standard plain | x / slide / deny | 11 | R2-I001 | - |
| standard plain | x / order / allow | 12 | I2-021, I2-022, I2-023, I2-035, R2-I001 | I2-037, R2-I013, R2-I018 |
| standard plain | x / order / deny | 12 | I2-021, I2-022, I2-023, I2-035, R2-I001 | I2-037, R2-I013, R2-I018 |
| standard plain | x / order_window / allow | 11 | I2-023, I2-029, I2-035, R2-I001 | I2-037, R2-I013, R2-I018 |
| standard plain | x / order_window / deny | 11 | I2-023, I2-029, I2-035, R2-I001 | I2-037, R2-I013, R2-I018 |
| standard window | budget / slide / deny | 21 | - | - |
| standard window | budget / order / allow | 21 | I2-012, I2-024, I2-027, I2-029, I2-034, I2-035, I2-042 | I2-004, I2-006, I2-022, I2-037, I2-043, R2-I013, R2-I018 |
| standard window | budget / order / deny | 21 | I2-012, I2-024, I2-027, I2-029, I2-034, I2-035, I2-042 | I2-004, I2-006, I2-022, I2-037, I2-043, R2-I013, R2-I018 |
| standard window | budget / order_window / allow | 24 | I2-012, I2-024, I2-025, I2-027, I2-029, I2-034, I2-035, I2-042 | I2-004, I2-006, I2-022, R2-I013, R2-I018 |
| standard window | budget / order_window / deny | 24 | I2-012, I2-024, I2-025, I2-027, I2-029, I2-034, I2-035, I2-042 | I2-004, I2-006, I2-022, R2-I013, R2-I018 |
| standard window | x / slide / allow | 22 | I2-023, R2-I001 | R2-I010 |
| standard window | x / slide / deny | 22 | I2-023, R2-I001 | R2-I010 |
| standard window | x / order / allow | 24 | I2-012, I2-021, I2-023, I2-024, I2-027, I2-034, I2-035, I2-042, R2-I001 | I2-004, I2-006, I2-043, R2-I010, R2-I013, R2-I018 |
| standard window | x / order / deny | 24 | I2-012, I2-021, I2-023, I2-024, I2-027, I2-034, I2-035, I2-042, R2-I001 | I2-004, I2-006, I2-043, R2-I010, R2-I013, R2-I018 |
| standard window | x / order_window / allow | 22 | I2-021, I2-023, I2-024, I2-025, I2-027, I2-034, I2-035, I2-042, R2-I001 | I2-004, I2-006, I2-013, I2-022, I2-043, R2-I010, R2-I013, R2-I018 |
| standard window | x / order_window / deny | 22 | I2-021, I2-023, I2-024, I2-025, I2-027, I2-034, I2-035, I2-042, R2-I001 | I2-004, I2-006, I2-013, I2-022, I2-043, R2-I010, R2-I013, R2-I018 |

## seat_empty_axis allow against deny: questions whose answer (the entries' words, the verdict) differs between the two, per run and (arm_cap, z_deep)

| run | budget / slide | budget / order | budget / order_window | x / slide | x / order | x / order_window |
|---|---|---|---|---|---|---|
| fast plain | 0 of 94 | 0 of 94 | 0 of 94 | 0 of 94 | 0 of 94 | 0 of 94 |
| fast window | 0 of 94 | 0 of 94 | 0 of 94 | 0 of 94 | 0 of 94 | 0 of 94 |
| standard plain | 0 of 94 | 0 of 94 | 0 of 94 | 0 of 94 | 0 of 94 | 0 of 94 |
| standard window | 0 of 94 | 0 of 94 | 0 of 94 | 0 of 94 | 0 of 94 | 0 of 94 |

## Check against the G3-f records (g3/s1flat/results/flat_*): the cells budget / slide / allow and budget / order / allow must give the same answers

| run | cell | questions in both | same verdict and same entries (words, centres, window) | different |
|---|---|---|---|---|
| fast plain | budget / slide / allow | 94 | 94 | 0 |
| fast plain | budget / order / allow | 94 | 94 | 0 |
| fast window | budget / slide / allow | 94 | 94 | 0 |
| fast window | budget / order / allow | 94 | 94 | 0 |
| standard plain | budget / slide / allow | 94 | 94 | 0 |
| standard plain | budget / order / allow | 94 | 94 | 0 |
| standard window | budget / slide / allow | 94 | 94 | 0 |
| standard window | budget / order / allow | 94 | 94 | 0 |

