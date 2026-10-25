await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const cfg = await eda.pcb_Drc.getCurrentRuleConfiguration();
const out = {};
out.same = await eda.pcb_Drc.overwriteCurrentRuleConfiguration(cfg);
const c2 = JSON.parse(JSON.stringify(cfg));
const ss = c2.config.Spacing['Safe Spacing'];
const base = ss.copperThickness1oz;
const hv = JSON.parse(JSON.stringify(base)); hv.editName = 'HV'; hv.isSetDefault = false;
for (const k of Object.keys(hv.tables)) hv.tables[k].content = hv.tables[k].content.map(r => r.map(() => 2.5));
ss.HV = hv;
out.withHV = await eda.pcb_Drc.overwriteCurrentRuleConfiguration(c2);
const c3 = JSON.parse(JSON.stringify(c2));
const tr = c3.config.Physics.Track;
for (const [n, mn, df] of [['PWR', 0.3, 0.5], ['HVT', 0.3, 0.4]]) {
  const t = JSON.parse(JSON.stringify(tr.copperThickness1oz)); t.editName = n; t.isSetDefault = false;
  for (const k of Object.keys(t.form.data)) { t.form.data[k].minValue = mn; t.form.data[k].defaultValue = df; }
  tr[n] = t;
}
out.withTrack = await eda.pcb_Drc.overwriteCurrentRuleConfiguration(c3);
const now = await eda.pcb_Drc.getCurrentRuleConfiguration();
out.nowSpacing = Object.keys(now.config.Spacing['Safe Spacing']);
out.nowTrack = Object.keys(now.config.Physics.Track);
return out;
