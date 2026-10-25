await eda.dmt_EditorControl.openDocument('78286f62bfd019a0');
const comps = await eda.sch_PrimitiveComponent.getAll('part');
const wires = await eda.sch_PrimitiveWire.getAll();
const out = {};
for (const c of comps) {
  const d = c.getState_Designator();
  (out[d] = out[d] || []).push({ id: c.getState_PrimitiveId(), x: c.getState_X(), y: c.getState_Y(), lcsc: c.getState_SupplierId(), bom: c.getState_AddIntoBom() });
}
return { n: comps.length, wires: wires.length, parts: out };
