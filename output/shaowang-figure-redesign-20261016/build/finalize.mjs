import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const build=path.dirname(fileURLToPath(import.meta.url));
const root=path.dirname(build);
const skill='C:/Users/yinha/.codex/plugins/cache/openai-primary-runtime/presentations/26.1013.11914/skills/presentations';
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')));
const result=await finalizePresentation({
 workspaceDir:root,
 candidatePath:path.join(build,'redrawn-draft.pptx'),
 finalPath:path.join(root,'deliverables','ShaoWang-报告配图重绘.pptx'),
 pythonExecutable:'C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','11430000,8001000','--require-native-table-slide','21','--require-native-table-slide','22'],
 explicitTotalSlideCount:29,
 requiredNativeTableOwnerSlides:[21,22],
 requiredNativeChartOwnerSlides:[],
 fontPolicy:{basis:'design',families:['Microsoft YaHei']},
 verifyArtifactToolImport:true,
 receiptPath:path.join(build,'pptx-validation.json')
});
console.log(JSON.stringify(result));
