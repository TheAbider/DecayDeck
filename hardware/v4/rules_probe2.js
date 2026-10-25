await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const cfg = await eda.pcb_Drc.getCurrentRuleConfiguration();
const out = {};
try { out.inner = await eda.pcb_Drc.overwriteCurrentRuleConfiguration(cfg.config); } catch (e) { out.inner = 'ERR ' + e; }
const ml = await eda.pcb_Drc.getRuleConfiguration('JLCPCB Capability(Multiple Layers Board)');
out.mlKeys = ml ? Object.keys(ml) : null;
try { out.ml = await eda.pcb_Drc.overwriteCurrentRuleConfiguration(ml); } catch (e) { out.ml = 'ERR ' + e; }
try { out.mlInner = ml && ml.config ? await eda.pcb_Drc.overwriteCurrentRuleConfiguration(ml.config) : null; } catch (e) { out.mlInner = 'ERR ' + e; }
out.name = await eda.pcb_Drc.getCurrentRuleConfigurationName();
return out;
