await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const lines = await eda.pcb_PrimitivePolyline.getAll(undefined, 13);
const glass = lines.filter(p => Math.abs(p.getState_LineWidth() - 6) < 0.01).map(p => p.getState_PrimitiveId());
if (glass.length) await eda.pcb_PrimitivePolyline.delete(glass);
return { removed: glass.length, left: lines.length - glass.length };
