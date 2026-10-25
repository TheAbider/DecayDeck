await eda.dmt_EditorControl.openDocument('6098964f68a86131');
await new Promise(r => setTimeout(r, 1000));
const ok = await Promise.race([eda.pcb_Document.importChanges('47e42882ab43173c', true), new Promise(r => setTimeout(() => r('PENDING'), 20000))]);
return ok;
