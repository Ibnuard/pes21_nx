# FootballNX27 brand

The human supplied the existing stacked Football / NX26 logo as the shape
reference and requested NX27 with white, blue and red. White custom pages use
charcoal letters. The large overlapping X and the small arrow wedge remain.

`brand-logo-source-v27.png` is the selected imagegen edit, on transparent alpha.
The earlier white-letter trials had poor transparency and were not used.
The selected dark-letter variant preserves clean solid lettering. Source art
is only cropped and resized into the 1120×405 runtime PNG; no glyphs are
redrawn by the asset builder. Source and runtime alpha remain independent of
the background. The compact scoreboard uses the dark variant on white.

The UI shader uses neutral RGB spread to adapt the letters to the requested
white or charcoal draw colour. Saturated blue/red samples retain their RGB.
This uses the existing texture sample and draw; it adds no texture or pass.
The existing all-colour alpha tint mode remains available for other sprites.

Selected imagegen prompt (edit mode, transparent background):

> Produce the light-background version of the supplied existing logo,
> rebranded FootballNX27. Preserve the broad rounded block typeface and
> stacked composition: Football above NX27. Replace 26 with 27. All Football
> letters, N and digits 27 are dark charcoal #1A2029, not white. Big X blue
> #125BFF, tiny arrow wedge red #EC2440. Clean opaque shapes on transparent
> alpha; no screenshot text, gradients or texture. Preserve the overlapping
> N/X and original broad proportions, with safe transparent margins.

Generation output: `exec-7b40fac4-1d5d-4662-b699-bab9d420649a.png`.
The selected output was copied into this directory. Menu images and scoreboard
previews are host layout evidence, not Switch captures.
