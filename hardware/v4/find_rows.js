await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const c of comps) {
  const des = c.getState_Designator();
  const pins = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
  if (!pins || pins.length < 6) continue;
  const ys = pins.map(p => p.getState_Y()), xs = pins.map(p => p.getState_X());
  out.push([des, Math.round(c.getState_X()), Math.round(c.getState_Y()), pins.length, Math.round(Math.min(...ys)), Math.round(Math.max(...ys)), Math.round(Math.max(...xs) - Math.min(...xs))]);
}
return { n: comps.length, rows: out };
