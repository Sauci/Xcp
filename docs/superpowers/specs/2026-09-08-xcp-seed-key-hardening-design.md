# Seed-and-key hardening — design

**Date:** 2026-09-08
**Status:** design, approved in outline; not yet planned or implemented
**Predecessors:** `2026-09-07-xcp-shared-state-defects-design.md` (DD70–DD77), whose §3b left one
defect deliberately unfixed and whose DD73 is what makes the fix below possible.

Three defects in one subsystem, all pre-existing, all shipped, and all answering the same
question badly: **what does `Xcp_Internal.protection_status` mean, and how long does it last?**
Because they share one field they share one design, and fixing any one alone would leave the
field's meaning half-changed.

---

## 0. Specification numbering

Every citation below was read in the 1.0 PDF via `pdftotext -layout` before being written down.
This section exists because four citation errors have been found on the immediately preceding
branch, one of which reached three shipped source comments.

| Cited as | Actual title |
|---|---|
| §1.6.1.1.3 | Get current session status from slave (GET_STATUS) |
| §1.6.1.2.4 | Get seed for unlocking a protected resource (GET_SEED) |
| §1.6.1.2.5 | Send key for unlocking a protected resource (UNLOCK) |
| §1.7.3.2.1 | Standard commands (STD) — the error/pre-action table |
| §1.7.3.2.2 | Calibration commands (CAL) — the error/pre-action table |

**A correction this design makes to existing code.** `source/Xcp.c` cites §1.7.3.2.2 for the
generic rule that a command addressing a locked resource answers `ERR_ACCESS_LOCKED`. §1.7.3.2.2 is
the *CAL* error table; the generic rule is in **§1.6.1.1.3**, which states it once per resource
group — "*all commands of the CALibration/PAGing group are protected and will return an
ERR_ACCESS_LOCKED upon an attempt to execute the command without a previous successful
GET_SEED/UNLOCK sequence*", and likewise for DAQ/STIM and PGM. Narrow citation, general claim.

That §1.6.1.1.3 defines **both** the protection mask's meaning and the refusal it causes is the
observation the whole design turns on.

---

## 1. What is wrong today

### D-A — an unlock is spent by the next command

`source/Xcp.c`, immediately after every successful dispatch:

```c
if (pid != XCP_PID_CMD_UNLOCK) {
    Xcp_ClearProtectionStatus();
}
```

So a granted resource survives exactly one following command — and not only a command that *used*
the grant: an unrelated `GET_STATUS` spends it identically. §1.6.1.2.5 says the opposite, that "*a
repetition of an UNLOCK sequence with a correct key will have a positive response and no other
effect*", which presumes the grant is still standing to be re-granted.

**Its worst consequence is already recorded as a generation refusal.** With PGM protected,
`PROGRAM_START` spends the unlock; the session becomes `XCP_PGM_ACTIVE`; `PROGRAM_RESET` — the only
command that ends it — is locked again; and `GET_SEED`/`UNLOCK` are themselves refused
`ERR_PGM_ACTIVE`. The slave cannot leave the programming session. `script/source_cfg.c.jinja2`
therefore *refuses to generate* `resource_protection.programming: true` at all. A configuration the
schema accepts and `CONNECT` advertises cannot be built.

### D-B — `UNLOCK` never asks whether a seed is held

Its only gate is `last_pid ∈ {GET_SEED, UNLOCK}`, which is about *sequence*. §1.6.1.2.5 is explicit:
"*The master only can send an UNLOCK sequence if previously there was a GET_SEED sequence… If the
master does not respect this sequence, the slave returns an ERR_SEQUENCE.*" Three routes were
measured on the fixed tree of the previous branch, all reaching `Xcp_CalcKey` with a zero-length
seed and all granting the resource.

The enforcement mechanism already exists and nothing consults it: `source/Xcp_Std.c` zeroes
`seed.total_length` once a full key arrives, under the comment "*enforces a new seed to be requested
prior to unlock a next resource*". DD73 — which stopped `GET_SEED` zeroing the same field — is what
makes it trustworthy enough to read.

### D-C — the protection mask is reported inverted, at three sites

§1.6.1.1.3 defines the Current Resource Protection Status as a mask where **1 = the group is
protected**, and §1.6.1.2.5 makes `UNLOCK`'s positive response carry that same mask. The module
writes `Xcp_GetProtectionStatus()` — the *unlocked* set — into `UNLOCK`'s complete-key response
byte 1, its partial-key response byte 1, and `GET_STATUS` byte 2.

Wrong in direction and in domain. In the default build, where nothing is configured protected,
unlocking PGM makes `GET_STATUS` report `0x10`: **PGM is protected**, claimed in a build where it is
not, at the moment it was granted. The configured mask `Xcp_Ptr->general->protectedResource` is read
in exactly one place — the dispatch gate — and by no reporting site at all, which is *why* the
polarity is wrong rather than merely reversed.

---

## 2. Design decisions

### DD78 — the field stores the still-locked mask, and is renamed to force that

`Xcp_Internal.protection_status` (the unlocked set) becomes `Xcp_Internal.locked_resource`, holding
the Current Resource Protection Mask exactly as §1.6.1.1.3 defines it. The accessors follow:
`Xcp_GetProtectionStatus`/`Xcp_SetProtectionStatus` become
`Xcp_GetLockedResources`/`Xcp_UnlockResources(mask)`, and `Xcp_ClearProtectionStatus` is deleted
along with its single call site.

**The rename is a safety mechanism, not tidying.** The field's meaning inverts, so every existing
reader must be revisited; renaming turns all of them into compile errors rather than silently
correct-looking arithmetic. An alternative was considered and rejected — keep the field meaning
"unlocked" and compute `protectedResource & ~protection_status` at each reporting site — because it
preserves exactly the property that caused D-C: a field whose readers must remember to invert it.
Three chances to get polarity wrong become zero when the stored value *is* the wire value.

### DD79 — an unlock lasts the session

Four writes, and no others:

| Where | What |
|---|---|
| `Xcp_Init` | `locked_resource = Xcp_Ptr->general->protectedResource` |
| `CONNECT` | the same re-seed, joining DD77's teardown block |
| `UNLOCK`, on success | `locked_resource &= ~requested_protected_resource` |
| nowhere else | — |

`Xcp_Ptr` is assigned before the initialisation block that will hold the first write, and that block
already dereferences it, so seeding from configuration there is safe and matches the existing
pattern.

D-A is then fixed by construction rather than by a rule: with no clear-after-dispatch there is
nothing to spend, and the session boundary is the only thing that re-locks. `&=` also makes grants
accumulate, so unlocking DAQ after PGM keeps both — which the current assignment would not have
done once grants began to persist.

`requested_protected_resource` keeps its present job: `GET_SEED` records which resource the seed was
issued for, `UNLOCK` grants exactly that.

### DD80 — the dispatch gate collapses to one term

```c
/* allowed iff no group this command belongs to is still locked */
if ((Xcp_PIDToCmdGroupTable[pid] & Xcp_Internal.locked_resource) == 0x00u)
```

replacing `((group & protectedResource) == 0) || ((group & unlocked) != 0)`. A resource never
configured protected is never in the mask, so the first term is subsumed.

**The equivalence was checked, not assumed.** Every one of `Xcp_PIDToCmdGroupTable`'s entries
carries exactly one group bit or `NONE` — the only values appearing are `MASK_CAL_PAG`, `MASK_DAQ`,
`MASK_PGM` and `MASK_NONE` — so old and new agree for every PID. They diverge only on a
hypothetical multi-bit entry, where the old form means "any one of its groups is unlocked" and the
new means "all of them are". The new reading is the safe one, and the single-bit property is
recorded as an invariant the table must keep.

### DD81 — `UNLOCK` requires a held seed

One added conjunct on the existing admission gate:

```c
if (((Xcp_Internal.last_pid == XCP_PID_CMD_GET_SEED) || (Xcp_Internal.last_pid == XCP_PID_CMD_UNLOCK)) &&
    (Xcp_Internal.seed.total_length != 0x00u))
```

The terms answer different questions and both are load-bearing. `last_pid` asks whether the
immediately preceding command was a successful `GET_SEED` or a prior frame of this same key — it
cannot distinguish which, being a two-element set-membership test, which is why a prediction that it
could was wrong on the previous branch. `seed.total_length` asks whether a seed exists and is
unspent. It stays non-zero across a multi-frame key and is zeroed only on completion, so it admits
every legitimate frame and refuses every D-B route.

`ERR_SEQUENCE` is the answer and needs **no deviation**: it is in `UNLOCK`'s own §1.7.3.2.1 row, and
that row's prescribed pre-action for it is `GET_SEED` — the refusal tells the master exactly what to
do next.

**A sentence that must not be misread.** §1.6.1.2.5's "*a repetition of an UNLOCK sequence with a
correct key will have a positive response and no other effect*" does not require a bare repeated
`UNLOCK` to succeed. The preceding sentence defines an UNLOCK sequence as one preceded by a
GET_SEED sequence, so a repetition is `GET_SEED`→`UNLOCK` again; "no other effect" means it must not
re-lock or otherwise disturb an already-granted resource, which `&= ~granted` gives for free.

### DD82 — the three reporting sites emit the mask directly

`UNLOCK`'s complete-key response byte 1, `UNLOCK`'s partial-key response byte 1, and `GET_STATUS`
byte 2 all become `Xcp_GetLockedResources()` with no arithmetic. Under DD78 the stored value is
already the wire value.

### DD83 — the programming generation refusal is removed; STIM's is not

Every link in the refused dead end depended on the unlock being spent. Under DD79 `PROGRAM_RESET`
stays unlocked, the chain never forms, and `GET_SEED`/`UNLOCK` remaining refused during
`XCP_PGM_ACTIVE` becomes harmless because no re-unlock is needed. The `raise` in
`script/source_cfg.c.jinja2` is deleted, and its obsolescence is *proved by an end-to-end test*
rather than argued (§5).

The second refusal in the same generator — `resource_protection.data_stimulation`, DD41/DD48 — is
**untouched and stays**. It exists because `Xcp_PIDToCmdGroupTable` maps every DAQ command to
`MASK_DAQ`, so no command is gated on `MASK_STIM` and a STIM protection would be advertised but not
enforced. That is command-group mapping work, unrelated to lifetime or polarity.

---

## 3. What this does not change

- The wrong-key path still answers `ERR_ACCESS_LOCKED` and disconnects, per §1.6.1.2.5. With
  DD74/DD77's teardown re-seeding the mask, a bad key now genuinely re-locks everything.
- DD76's `ERR_GENERIC` branch for a failing `Xcp_CalcKey` is unchanged.
- `GET_SEED`'s own behaviour, including DD72's rollback and DD73's length handling.
- The `Xcp_CTOErrorMatrix`, except where a newly reachable error code requires a row bit.
- `CONNECT`'s RESOURCE byte, which reports available resources and is a different byte from the
  protection mask.

---

## 4. Test strategy

**The existing security tests get stronger, not merely updated, and this is a correction rather than
churn.** `test/seed_key_defects_test.py` proves the DD72 bypass by watching `protection_status` go
non-zero — a status byte, in a build where `DefaultConfig` leaves every `resource_protection_*`
false, so the feature under test is switched off. Under DD78 that observable correctly disappears,
which forces the better one: configure `resource_protection.calibration_paging: true`, and a bypass
becomes visible as *a CAL command running when it should have answered `ERR_ACCESS_LOCKED`*.
Behaviour, not bookkeeping. This is the same failure that hid two of the six defects on the previous
branch — a test double that cannot observe the value under test.

New tests, each pinning one claim:

| Claim | Shape |
|---|---|
| An unlock persists | unlock CAL_PAG, run several unrelated commands, a CAL command is still accepted |
| …but not across sessions | unlock, `CONNECT`, the CAL command answers `ERR_ACCESS_LOCKED` |
| Unlocks accumulate | unlock CAL_PAG then DAQ; commands of both groups remain accepted |
| No seed, no unlock | `UNLOCK` with no preceding `GET_SEED` → `ERR_SEQUENCE` |
| A spent seed is spent | a completed `UNLOCK`, then `UNLOCK` again → `ERR_SEQUENCE` |
| The mask is the wire format | with protection configured, `GET_STATUS` byte 2 and `UNLOCK` byte 1 report the *still-locked* set |
| The refusal is obsolete | the end-to-end sequence of §5 |

**Mutation verification is required on four points**, the change being security-relevant throughout:
the gate expression of DD80; **each of DD81's two conjuncts separately** — a compound condition needs
a test per term, not per outcome; and at least one DD82 reporting site.

**One honest limit.** `Xcp_PIDToCmdGroupTable` is `static` in `source/Xcp.c` and is therefore no more
reachable from the CFFI harness than `Xcp_Internal` is, so DD80's single-bit invariant cannot be
asserted directly. It gets a stated invariant in the comment and indirect behavioural coverage —
unlocking one resource must not make another group's commands reachable. That is weaker than a
direct check, and the plan should say so rather than imply the invariant is tested.

---

## 5. Acceptance

1. Each of D-A, D-B and D-C has a test that fails on the current code and passes after the fix.
2. **The end-to-end proof that DD83's refusal is obsolete:** with `resource_protection.programming:
   true` and `programming.enabled: true`, the sequence `CONNECT` → `GET_SEED(PGM)` → `UNLOCK` →
   `PROGRAM_START` → `PROGRAM_CLEAR` → `PROGRAM` → `PROGRAM_RESET` completes, every step answering
   positively. This configuration cannot be built at all today.
3. The four mutation verifications of §4 are carried out and recorded, each naming which test failed.
4. `./test.sh` green in the CI container, both ctest targets, on a clean build tree.
5. No new instance of the recurring test-authoring traps, and no test whose name claims a property
   its assertions cannot fail on.
6. The `resource_protection.data_stimulation` refusal still fires, with its own test unchanged.
