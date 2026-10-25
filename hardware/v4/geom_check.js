await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const pads = await eda.pcb_PrimitivePad.getAll();
const holes = pads.filter(p => !/e\d+e\d+/.test(p.getState_PrimitiveId()) && p.getState_Hole()).map(p => [+(p.getState_X() * 0.0254).toFixed(2), +(p.getState_Y() * 0.0254).toFixed(2)]);
const comps = await eda.pcb_PrimitiveComponent.getAll();
const want = ['U1', 'J4'];
const c = {};
for (const x of comps) if (want.includes(x.getState_Designator())) {
  const pins = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(x.getState_PrimitiveId());
  const xs = pins.map(p => p.getState_X() * 0.0254), ys = pins.map(p => p.getState_Y() * 0.0254);
  c[x.getState_Designator()] = { pinSpanX: +(Math.max(...xs) - Math.min(...xs)).toFixed(2), pinSpanY: +(Math.max(...ys) - Math.min(...ys)).toFixed(2), x: +(x.getState_X() * 0.0254).toFixed(2), y: +(x.getState_Y() * 0.0254).toFixed(2) };
}
return { holes, c };
