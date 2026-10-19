import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const build=path.dirname(fileURLToPath(import.meta.url));
const root=path.dirname(build);
const skill='C:/Users/yinha/.codex/plugins/cache/openai-primary-runtime/presentations/26.1013.11914/skills/presentations';
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')));
const result=await finalizePresentation({workspaceDir:root,candidatePath:path.join(build,'figures-draft.pptx'),finalPath:path.join(root,'deliverables','ShaoWang-图源.pptx'),pythonExecutable:'C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','5715000,4000500'],explicitTotalSlideCount:30,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],fontPolicy:{basis:'user_request',families:['SimSun','Times New Roman']},verifyArtifactToolImport:true,receiptPath:path.join(build,'pptx-validation.json')});
console.log(JSON.stringify(result));

