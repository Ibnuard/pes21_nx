# Shared competition action sprites

`actions-v1.png` is the original generated flat 2D sprite sheet used by Cup and
League. It uses white, blue and red, with actual alpha transparency. The shared
`competition_ui_pattern` renderer keeps native aspect and applies 20% opacity
as a partially clipped bottom-right background pattern in the New/Continue cards and Hub action cards in both modes.

The image is generated and recolored with built-in image_gen. Exact generation
and final recolor prompts are recorded in `../league/manifest.json` under
`../competition/actions-v1.png`. Identical PNG bytes are linked by bin2o as
`data/competition_actions_v1.bin`.
