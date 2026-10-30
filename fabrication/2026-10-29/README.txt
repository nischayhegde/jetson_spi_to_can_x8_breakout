SPI to eight-channel CAN breakout - fabrication files
Export date: 2026-10-29. KiCad 10.0.7.

Finished outline: 81 x 80 mm, measured at the outline centerline.
Board: four copper layers, nominal 1.6 mm FR4.
The saved nominal copper thickness is 0.035 mm on each copper layer.

Copper order, top to bottom:
  L1  breakout-Top.gtl        F.Cu   Top
  L2  breakout-GND.g1         In1.Cu GND
  L3  breakout-PWR.g2         In2.Cu PWR
  L4  breakout-Bottom.gbl     B.Cu   Bottom

Other Gerbers:
  breakout-F_Mask.gts / breakout-B_Mask.gbs: solder mask openings.
  breakout-F_Silkscreen.gto / breakout-B_Silkscreen.gbo: silkscreen.
  breakout-Edge_Cuts.gm1: single closed board perimeter.
  breakout-F_Paste.gtp / breakout-B_Paste.gbp: optional stencil layers.

Drills: Excellon, millimeters, absolute origin matching the Gerbers,
unmirrored; plated and non-plated holes are separate:
  breakout-PTH.drl: 277 holes (207 x 0.30, 24 x 0.95, 46 x 1.00 mm).
  breakout-NPTH.drl: four 3.20 mm non-plated M3 mounting holes.
The mounting-hole center spacing is 73 x 72 mm, 4 mm from board edges.

Gerbers use X2 attributes and 4.6 absolute metric coordinates. Copper zones
were checked/refilled in memory before plotting. Silkscreen is clipped out
of solder-mask openings during export. The source CAD files were unchanged.

breakout-job.gbrjob records layer functions and the saved nominal stackup.
Its 81.05 x 80.05 mm size includes the 0.05 mm outline stroke; the actual
board perimeter centerline in breakout-Edge_Cuts.gm1 is 81 x 80 mm.
The source does not specify a surface finish (job Finish="None"); select
the surface finish when placing the fabrication order.

Pre-export DRC with zones refilled: zero violations, zero unconnected
items and zero schematic/PCB parity issues under the project settings.
Every exported drill hit was compared against its source pad or via.
The export contains no changes to the electrical design or board geometry.
