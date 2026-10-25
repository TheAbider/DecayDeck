await eda.dmt_EditorControl.openDocument('6098964f68a86131');
await new Promise(r => setTimeout(r, 500));
const s = await Promise.race([eda.sys_FileManager.getDocumentFootprintSources(), new Promise(r => setTimeout(() => r('TIMEOUT'), 20000))]);
return Array.isArray(s) ? s.map(x => ({ uuid: x.footprintUuid, src: x.documentSource })) : s;
