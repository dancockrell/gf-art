# Ghost Front — art

Sprite frames for [Ghost Front](../ghost-front). 111 PNGs, organised one
directory per unit, one file per animation frame.

## Naming

```
UNIT/state_N.png        e.g.  HAWKEB/run_2.png
```

`state` is the animation (`idle`, `walk`, `run`, `crouch`, `jump`, `aim`,
`fire`, `reload`, `attack`, `lunge`, `death`) and `N` is the frame number
within it, starting at 1.

## Units

| Unit | Frames | States |
|---|---|---|
| `HAWKEB` | 11 | crouch, idle, jump, reload, run |
| `HAWKEA` | 8 | idle, run, walk |
| `PANZERHUND` | 5 | death, idle, lunge, run |
| `JAEGER` | 4 | aim, death, fire, idle |
| `MGTEAM` | 3 | fire, reload |
| `PANZER` | 3 | attack, walk |
| `CHIMAERE`, `EISWITWE`, `KNOCHEN`, `PENDEL`, `TRUEMMER` | 2 each | death |

## Other directories

- `refs/` — single reference frames per unit, including `DIREKTOR1` and
  `DIREKTOR2`, used as input when generating new poses
- `r2/`, `r3/` — later regeneration rounds for units that needed rework

## Where these come from

Frames are cut from annotated art plates by
[`gf-pipeline`](../gf-pipeline), which extracts rows and frames from a
sheet and reduces them to an indexed palette the game can draw:

```python
import extract, reduce
rows = extract.cut('SHEET.jpg')
tables, pal = reduce.make_table(rows[0], target_h=52, ncol=12)
print(reduce.js_literal('SCHUETZE', tables, pal, den=2))
```

The generation side lives in [`gf-forge`](../gf-forge), which drives
ComfyUI from scripts rather than the node graph.

## Licence

These are generated images and are **not licensed for reuse**. See
[LICENSE](LICENSE).
