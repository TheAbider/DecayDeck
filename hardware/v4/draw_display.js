await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const MIL = 1 / 0.0254;
const old = await eda.pcb_PrimitivePolyline.getAll(undefined, 13);
if (old.length) await eda.pcb_PrimitivePolyline.delete(old.map(p => p.getState_PrimitiveId()));
const rect = (x0, y0, x1, y1) => eda.pcb_MathPolygon.createPolygon(['R', x0 * MIL, y1 * MIL, (x1 - x0) * MIL, (y1 - y0) * MIL, 0, 0]);
const a = await eda.pcb_PrimitivePolyline.create('', 13, rect(-31.242, -40.64, 31.242, 40.64), 8);
const b = await eda.pcb_PrimitivePolyline.create('', 13, rect(-22.6, -31.6, 22.6, 38.0), 6);
const t = await eda.pcb_PrimitiveString.create(13, -20 * MIL, 2 * MIL, 'ADAFRUIT 2090 DISPLAY 81.3 x 62.5 mm', 'default', 60, 6, 4, 0, false, 0, false, false);
return { board: !!a, glass: !!b, label: !!t };
