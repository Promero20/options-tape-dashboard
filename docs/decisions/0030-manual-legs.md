# 0030. Manual legs: one per operation, entered in tab 2, edited and deleted from tab 1

- **Date:** 2026-10-29
- **Status:** accepted (completes the specification)

## Context

The specification has the missing leg added in tab 2, with the underlying already filled in, and says that a manual leg can be edited or deleted later and that deleting it sends the operation back to tab 2. It does not say where it is edited, how many legs an operation can get, or what happens to the operation type chosen with the leg ([0011](0011-manual-leg-operation-type.md)). In the real data there are between 5 and 17 pending operations above the threshold per capture, and every one has exactly one known leg.

## Decision

- **One manual leg per operation.** The specification speaks of "the missing leg", and with a third leg the operation would be discarded anyway.
- **The form starts from the known leg**: its type, expiration and size are filled in, and the user types the strike and the price. While it is being filled in, it shows the operation types that fit both legs and a preview of the result (structure, destination, strike and premium).
- **The operation type is required**, with "Don't know" among the options. Without a type the manual leg has no side, and the operation would end up as an undetermined multi-leg without the user having decided it.
- **Tab 2 lists only pending operations.** A completed operation is edited or deleted from its pop-up in tab 1, where it now appears.
- **Deleting the manual leg also deletes the operation type** chosen with it, and the operation goes back to tab 2. Clearing only the type keeps the leg, and the operation becomes an undetermined multi-leg.
- **Nothing is deleted silently.** If a stored leg can no longer be applied (for example, because it repeats a contract the rebuilt operation now has), the operation is pending again with a note that says why, and saving from tab 2 replaces that leg.

## Rejected alternatives

- **Several manual legs per operation**: more form for operations that would be discarded anyway.
- **A list of completed operations in tab 2**: two places for the same operation; the user preferred to edit them where they are classified.
- **Keeping the operation type when the leg is deleted**: it would be applied to whatever leg is entered next, or show up as a type that no longer fits.

## Consequences

- Operations completed by hand carry the edited mark (✎) in tab 1, and their manual leg is marked in the legs table.
- The tab 1 pop-up has a third kind of editor, next to direction and operation type.
