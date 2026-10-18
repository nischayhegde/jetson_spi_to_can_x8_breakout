# BreakoutBoard active schematic library

Cleaned on 2026-10-18 against `../breakout/breakout.kicad_sch`. The current bundle contains **20 standalone MPN symbols, 14 footprints and 14 STEP models**. Quantities in `parts.json` and `asset_manifest.csv` now count the placed parts in the common-ground schematic, with the requested 1 A input fuse retained for a reported correction. These files describe library usage; missing test-point packages and unresolved review findings mean they are not a released manufacturing BOM.

Read [the latest schematic review](../review/latest/schematic_review.txt) before layout. The schematic was left unchanged. The latest user-saved revision correctly powers all four logic ICs and their bypass capacitors at 3.3 V. The requested 1 A series fuse is still absent, and 79 footprint fields are blank.

## What was retained

- The 12 MPN symbol types actually placed from `BreakoutBoard`, including the CAN IC, crystals, 100 nF capacitors, connectors, LDO, OR/NOT/NAND logic, MOSFET and gate Zener.
- Seven selected MPN aliases and their packages for generic capacitors/resistors already placed in the schematic. Blank footprint fields do not make these packages unused.
- `0466001.NR`: the requested 1 A, 1206 input fuse, retained to restore the missing series fuse.

`RC0603FR-07100KL` is the matching 100 kohm, 1%, 0.1 W, 0603 alias for R34-R37. Its package is shared with the other 0603 resistors. [DigiKey](https://www.digikey.com/en/products/detail/yageo/RC0603FR-07100KL/729836), [YAGEO specification](https://yageogroup.com/component-documentation/download/specsheet/RC0603FR-07100KL). The saved YAGEO RC_L family sheet at `../datasheets/RC0603FR-0710KL.pdf` also documents this resistor family.

The seven generic C/R mappings are:

| Schematic value | Selected MPN | Local footprint |
|---|---|---|
| 27 pF | CL10C270JB8NNNC | C_0603_1608Metric |
| 1 uF | CGA3E1X7R1E105K080AC | C_0603_1608Metric |
| 10 uF | CL21B106KOQNNNE | C_0805_2012Metric |
| 33 ohm | RC0603FR-0733RL | R_0603_1608Metric |
| 10 kohm | RC0603FR-0710KL | R_0603_1608Metric |
| 100 kohm | RC0603FR-07100KL | R_0603_1608Metric |
| 120 ohm | RC1206FR-07120RL | R_1206_3216Metric |

These mappings preserve the intended assets; they do not assign footprints to the schematic automatically. There are still 79 blank footprint fields, including 23 test points whose mechanics must be chosen.

## Removed assets and recovery

Removed the abandoned isolator/converter/eFuse selections, unused AND gate, external CAN TVS, old diode/fuse/capacitor aliases, unplaced termination jumper and old SG-210STF powered-oscillator import bundle. Shared SOT-23, TSSOP-14 and passive packages were preserved for the parts still using them. Unused SVG previews were removed too.

`cleanup_manifest.json` lists every removed file, the 12 removed main-library aliases, every retained asset and the placed references/reason for each component. The complete folder before cleanup is saved in [library-before-cleanup.zip](../review/latest/library-before-cleanup.zip), outside this active library directory. The main component list and CSV are synchronized to this active nonisolated inventory; archived component lists and datasheets remain separately available.

## Use in KiCad

Open `../breakout/breakout.kicad_pro` in KiCad 9 or newer. Its existing symbol-library table already registers `BreakoutBoard.kicad_sym`. The missing `../breakout/fp-lib-table` has now been added and registers `BreakoutBoard.pretty` using a project-relative path. Restart the editor or reload libraries if it was already open.

The supplied `sym-lib-table` and `fp-lib-table` here are templates for the existing `breakout/` project location. Merge entries rather than overwriting other project libraries. Footprint model paths use `${KIPRJMOD}/../kicad_footprints/3dmodels/`; keep that directory relationship. No separate STEP import is needed when these local footprints are assigned to the PCB.

## Files and reproducibility

- `BreakoutBoard.kicad_sym`: 20 standalone symbols with expanded inheritance.
- `BreakoutBoard.pretty/` and `3dmodels/`: 14 packages and matching local nominal STEP models.
- `parts.json` / `asset_manifest.csv`: MPN, quantity, placed references, retention reason, package/model mapping and dated sourcing evidence.
- `sha256.json`: checksums of the retained CAD assets.
- `validation/report.txt`: KiCad loading, pin/pad coverage, specific pin identities, STEP signatures and checksums.
- `validation/symbols/`: current previews exported by KiCad's symbol parser.
- `library_usage.py`: reads placed symbols and maps generic passives without editing the design.
- `build_library.py`: generates the active selection from the installed official KiCad libraries. The larger source catalog in this script is filtered against the live schematic.
- `prune_library.py`: dependency-based cleanup, with a reviewable plan by default and explicit file deletion only with `--apply`.

To rebuild after deliberate schematic changes, run `python build_library.py`, inspect `python prune_library.py`, then run `python prune_library.py --apply`. Validate with KiCad's bundled Python using `validate_library.py`, and export symbol SVGs with `kicad-cli sym export svg`. The cleanup tool checks resolved paths remain inside this folder and retains explicitly assigned PCB footprints too. Unknown generic passive values stop generation rather than silently losing their packages.

`write_component_list.py` renders the current nonisolated BOM/CSV from the active inventory, live reference counts, latest audit and `sourcing_updates.json`. It preserves the former component list under `../review/latest/`. The older `validation/bank_truth_table.json`, `shared_irq_truth_table.json` and `logic_timing_review.txt` describe the original isolated AND/NOT proposal. Current truth tables and review evidence are in `../review/latest/`.

## Provenance and limits

These assets derive from the installed official KiCad 9 distribution at `C:/Program Files/KiCad/9.0/share/kicad`, rather than supplier CAD-widget downloads. STEP files represent nominal package geometry and are not manufacturer-certified models of each MPN. Confirm package tolerances and connector heights before mechanical release.

The MCP251863 E/SS alias uses the official H/SS pin arrangement for the shared SSOP-28 package. The local library correctly declares TXD pin 23 as an input, per Microchip Table 1-1; the user's cached schematic symbol still needs that electrical-type correction. Do not delete the valid TXCAN15-to-TXD23 connection to silence ERC.

The selected OR, NOT and NAND symbols use compatible graphical symbols with actual MPN names and manufacturer links. The NAND's physical NC pads 9/10/13 are represented explicitly. Place every used logic unit and its power unit, powered at 3.3 V in this circuit. Updating cached symbols requires care to preserve the user's graphical edits.

AO3401A: pin1=G, pin2=S, pin3=D. Drain faces the fused input; source feeds protected 5 V. BZT52C6V8-13-F: pin1=K to the MOSFET source, pin2=A to the gate. R38 pulls the gate to GND. The Zener protects VGS, not the supply rail. Bulk capacitance stays after the MOSFET. The review documents the missing fuse and the limits of this simple reverse-hookup circuit.

## Attribution

Derived symbols, footprints and STEP models: [KiCad official libraries](https://www.kicad.org/libraries/), under the [KiCad library license and exception](https://www.kicad.org/libraries/license/). Original authors retain attribution. Local changes include MPN aliases, flattened inheritance, corrected pin electrical types and project-relative STEP references.

Validation establishes parsing, local asset availability and pin-number coverage. It does not certify electrical behavior, PCB routing, package tolerances or prototype performance.
