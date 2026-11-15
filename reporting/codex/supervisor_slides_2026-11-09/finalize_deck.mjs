import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const base='C:/Users/Felix/Documents/Codex/2026-11-08/can';
const build=path.join(base,'work/supervisor_slides_2026-11-09');
const skill='C:/Users/Felix/.codex/plugins/cache/openai-primary-runtime/presentations/26.1105.12137/skills/presentations';
const runtime='C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1105-1297-0_26.1105.1297.0_x64__3k8sg7r9htsxt/dependencies';
process.env.RUNTIME_NODE_MODULES=path.join(runtime,'node/node_modules');
const {importRuntimeModule}=await import(pathToFileURL(path.join(skill,'container_tools/runtime_helpers.mjs')).href);
const {Presentation,PresentationFile}=await importRuntimeModule('@oai/artifact-tool');
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const p=Presentation.load(JSON.parse(await fs.readFile(path.join(build,'presentation.json'),'utf8')));
const assets=path.join(base,'work/consolidated_report_2026-11-09/assets');
// Session asset references are transient. Embed the original bytes for local delivery.
for (const [index,name] of [[1,'one_sensor_patch.png'],[6,'review_01.png']]) {
 const image=p.slides.items[index].images.items[0];
 const frame=image.frame,crop=image.crop,fit=image.fit,alt=image.alt;
 image.replace({blob:new Uint8Array(await fs.readFile(path.join(assets,name))),contentType:'image/png',alt,fit});
 image.frame=frame;image.crop=crop;
}
for (const s of p.slides.items) for(const ch of s.charts.items) applyPresentationChartFont(ch,{fontFamily:'Arial'});
const candidate=path.join(build,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidate);
const result=await finalizePresentation({
 workspaceDir:base,candidatePath:candidate,finalPath:path.join(base,'outputs/FYP_Supervisor_Update_2026-11-09_v2.pptx'),
 pythonExecutable:path.join(runtime,'python/python.exe'),
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 requiredNativeChartOwnerSlides:[4,5,6],requiredNativeTableOwnerSlides:[],
 materializeLiteralChartWorkbooks:true,nativeChartTargetApplication:'powerpoint',
 fontPolicy:{basis:'design',families:['Arial']},verifyArtifactToolImport:true,
 receiptPath:path.join(build,'final_validation_v2.json')
});
console.log(JSON.stringify(result));
const {FileBlob}=await importRuntimeModule('@oai/artifact-tool');
const finalModel=await PresentationFile.importPptx(await FileBlob.load(result.finalPath));
for (let i=0;i<finalModel.slides.items.length;i++) {
 const png=await finalModel.export({slide:finalModel.slides.items[i],format:'png',scale:1});
 await fs.writeFile(path.join(build,'export-slide-'+(i+1)+'.png'),new Uint8Array(await png.arrayBuffer()));
}
