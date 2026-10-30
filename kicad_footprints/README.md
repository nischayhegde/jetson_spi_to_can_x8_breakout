# BreakoutBoard component library

Synchronized on 2026-10-29 with the saved KiCad schematic, PCB and purchasing lists. The active inventory contains **21 MPNs and 120 fitted packages**. All physical schematic components have footprints. F1 is present in series with the protected input. The 21 bare test pads and four board-only mounting holes require no purchased part.

The current change record and validation results are in [the standardization report](../review/standardization-2026-10-29/standardization-report.txt). Earlier files in `review/latest/` and the dated review folders describe historical revisions; their missing-fuse and missing-footprint statements do not describe the current design.

## Consistent component identities

- R6, R10, R13, R16, R23, R26, R29 and R32: YAGEO **RC1206FR-07120RL**, 120 ohm, 1%, 0.25 W, `BreakoutBoard:R_1206_3216Metric`.
- J1: Harwin **M20-7832046**, female 2 x 20, 2.54 mm through-hole socket, matching its existing female PCB footprint.
- TP13 and TP14: Harwin **M20-9990246**, male 1 x 2, 2.54 mm through-hole headers. Other test points are bare copper pads.
- The 28 bypass capacitors: **CC0603KRX7R9BB104**, displayed value `100n`, references C1 and C21-C47. Capacitor references are now C1-C47.
- Every purchased package carries explicit `MPN` and `Manufacturer` fields in both the schematic and PCB. Multi-unit ICs count as one package. Values and references are not used as substitutes for an MPN.

The 27 pF, 1 uF and 100 nF capacitors all use 0603 packages; C20 is 0805. The 33 ohm, 10 kohm and 100 kohm resistors remain 0603. Their differing values and ratings are intentional.

## Project assets

Open `../breakout/breakout.kicad_pro` with KiCad 10. The project library tables register the local symbol and footprint libraries using project-relative paths. PCB model paths use `${KIPRJMOD}/../kicad_footprints/3dmodels/`, including the female socket and test headers, so these models do not depend on a KiCad 9 environment variable.

- `BreakoutBoard.kicad_sym`: 21 standalone MPN aliases with expanded inheritance.
- `BreakoutBoard.pretty/` and `3dmodels/`: shared package assets, the mounting-hole footprint, and nominal STEP models. A retained asset is not necessarily a fitted purchase item; use the live inventory for quantities.
- `parts.json` and `asset_manifest.csv`: the 21 active MPNs, quantities, references and actual assigned footprint IDs.
- `sha256.json`: checksums for the local symbol library, footprint files and STEP models.
- `validation/report.txt`: symbol-to-pad numbering, key pin identities, STEP signatures and checksum verification.

The MCP251863 symbol declares TXD23 as input and RXD28 as output. AO3401A uses G1/S2/D3. The gate-clamp Zener uses K1/A2. These identities and the complete channel wiring were verified against the saved schematic and PCB.

## Updating the lists

Run `python -B kicad_footprints/write_component_list.py` from the repository root. This exports a fresh netlist, reconciles schematic/PCB fields, and regenerates both component lists and all order-list formats. It requires KiCad 10 and the Codex bundled Node/Artifact Tool runtime. Override runtime locations with `KICAD_BIN`, `CODEX_NODE` and `CODEX_ARTIFACT_NODE_MODULES` if needed.

Supplier data comes from the dated observations in `../review/orderlist-2026-10-29/supplier_quotes.json`. Regenerating the lists does **not** refresh stock or prices. All displayed stock and prices retain their observation date, and unverified Mouser entries remain labeled. Refresh supplier evidence deliberately before purchasing.

`../purchasing_config.json` records the approved purchasing substitute and the spare quantities used by the bulk-add text. On 2026-10-30, AC0603FR-0710KL replaced the unavailable RC0603FR-0710KL in the purchase list, using the same 0603 package and electrical ratings. The CAD MPN remains the original design identity; the list's `cad_mpn` column preserves that mapping. The saved schematic, PCB and fabrication ZIP are unchanged. The order plan contains 144 pieces for 120 fitted components, including 24 spares (20% overall).

The same purchasing configuration also substitutes Vishay CRCW0603100KFKEA for the backordered RC0603FR-07100KL at R34-R37. It is 100 kohm, 1%, 100 ppm/C, at least 0.1 W, and fits the existing 0603 footprint. Five are ordered for four fitted positions plus one spare; the DigiKey cut-tape SKU is 541-100KHCT-ND. This purchasing change does not alter the saved CAD or fabrication files.

`library_usage.py` follows the root schematic and its referenced child sheets, avoiding backups and history files. `build_library.py` can rebuild the active MPN aliases from installed official KiCad assets; review the resulting changes before replacing project assets. `validate_library.py` runs with KiCad's bundled Python. Rebuilding library defaults does not update placed PCB footprints automatically.

## Verification limits and attribution

Current ERC, PCB DRC and schematic/PCB parity checks have zero findings. The netlist before and after standardization has exactly the same pin-to-net connectivity. No project rules or exclusions were changed. These results do not establish SPI timing margin, independent power-sequence safety, thermal margin or EMC performance. The outstanding system qualification items from [the electrical review](../review/verification-2026-10-25/verification_report.txt) remain applicable except for explicitly resolved documentation and ground-pin items.

Derived symbols, footprints and STEP models come from the [official KiCad libraries](https://www.kicad.org/libraries/) under the [library license and exception](https://www.kicad.org/libraries/license/). Original authors retain attribution. Local modifications include MPN aliases, flattened inheritance, corrected electrical pin types and project-relative model paths. STEP files depict nominal package geometry and are not manufacturer-certified mechanical models.
