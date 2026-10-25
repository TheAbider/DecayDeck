await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const f = await Promise.race([eda.pcb_ManufactureData.getPdfFile('DecayDeck_v4_view'), new Promise(r => setTimeout(() => r(null), 25000))]);
if (!f) return null;
const buf = new Uint8Array(await f.arrayBuffer());
let s = '';
for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
return { name: f.name, size: buf.length, b64: btoa(s) };
