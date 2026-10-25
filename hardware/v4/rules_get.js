await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const out = {};
for (const [k, f] of [['name', () => eda.pcb_Drc.getCurrentRuleConfigurationName()], ['cfg', () => eda.pcb_Drc.getCurrentRuleConfiguration()],
  ['all', () => eda.pcb_Drc.getAllRuleConfigurations(true)], ['netRules', () => eda.pcb_Drc.getNetRules()],
  ['classes', () => eda.pcb_Drc.getAllNetClasses()], ['layers', async () => (await eda.pcb_Layer.getAllLayers()).map(l => [l.id, l.name, l.type])]]) {
  try { out[k] = await f(); } catch (e) { out[k] = 'ERR ' + e; }
}
return out;
