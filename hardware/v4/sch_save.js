await eda.dmt_EditorControl.openDocument('78286f62bfd019a0');
await new Promise(r => setTimeout(r, 500));
return await eda.sch_Document.save();
