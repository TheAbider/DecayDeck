await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const ol = await eda.pcb_PrimitivePolyline.getAll(undefined, 11);
const regs = await eda.pcb_PrimitiveRegion.getAll();
const f = p => { try { const poly = p.getState_Polygon(); return { src: poly.getSource ? poly.getSource() : poly, w: eda.pcb_MathPolygon.calculateWidth(poly), h: eda.pcb_MathPolygon.calculateHeight(poly) }; } catch (e) { return String(e); } };
return { outline: ol.map(f), regions: regs.map(r => ({ name: r.getState_RegionName(), layer: r.getState_Layer(), rule: r.getState_RuleType && r.getState_RuleType(), poly: f(r) })) };
