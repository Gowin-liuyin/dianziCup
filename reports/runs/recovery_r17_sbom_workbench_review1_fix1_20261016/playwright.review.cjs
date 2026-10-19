const path=require('node:path');
const root=path.resolve(__dirname,'../../..');
const {defineConfig}=require(path.join(root,'frontend/node_modules/@playwright/test'));
const diagnostic=process.env.R17_RECHECK_DIAGNOSTIC==='1';
module.exports=defineConfig({
  testDir:root,
  testMatch:[/frontend[\\/]e2e[\\/]r17_(sbom_fixture|assets_fixture|graph_app_fixture)\.spec\.ts$/,/recovery_r17_sbom_workbench_review1_fix1_20261016[\\/](reviewer_resource_adapter|acceptance)\.spec\.ts$/],
  grep:diagnostic?/MUST/:undefined,grepInvert:diagnostic?undefined:/MUST/,
  fullyParallel:false,workers:1,timeout:30000,expect:{timeout:7000},
  outputDir:path.join(__dirname,diagnostic?'edge_original_diagnostic':'edge_acceptance'),
  reporter:[['list'],['json',{outputFile:path.join(__dirname,diagnostic?'edge_original_diagnostic.json':'edge_acceptance.json')}]],
  use:{baseURL:'http://127.0.0.1:26573',browserName:'chromium',channel:'msedge',viewport:{width:1366,height:900},trace:'off',video:'off',screenshot:diagnostic?'only-on-failure':'off'},
  webServer:{command:'node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 26573 --strictPort',cwd:path.join(root,'frontend'),url:'http://127.0.0.1:26573',timeout:30000,reuseExistingServer:false}
});
